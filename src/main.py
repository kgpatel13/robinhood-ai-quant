from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd

from src.backtest import BacktestConfig, BacktestEngine
from src.common.config import load_settings, load_yaml, validate_all_configs
from src.common.exceptions import QuantPlatformError
from src.common.health import collect_health
from src.common.logging_config import configure_logging
from src.core.bootstrap import build_runtime
from src.core.context import ExecutionContext
from src.core.events import BacktestCompleted, MarketDataLoaded
from src.data.catalog import build_catalog
from src.data.demo import make_demo_bars
from src.data.service import MarketDataService
from src.data.storage import ParquetBarStore
from src.portfolio import PortfolioBacktestConfig, PortfolioBacktestEngine
from src.portfolio.models import AllocationMethod, RebalanceFrequency
from src.reporting import write_backtest_report, write_portfolio_report
from src.research import (
    OptimizationConfig,
    OptimizationEngine,
    ParameterSpec,
    write_optimization_report,
)
from src.strategies import available_strategies, create_strategy

LOGGER = logging.getLogger(__name__)


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD") from exc


def key_value(value: str) -> tuple[str, str]:
    key, separator, item = value.partition("=")
    if not separator or not key or not item:
        raise argparse.ArgumentTypeError("Value must use KEY=VALUE")
    return key, item


def parameter_spec(value: str) -> ParameterSpec:
    name, separator, raw_values = value.partition("=")
    if not separator or not name or not raw_values:
        raise argparse.ArgumentTypeError("Parameter must use NAME=VALUE1,VALUE2")
    try:
        values = tuple(int(item.strip()) for item in raw_values.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Parameter values must be integers") from exc
    try:
        return ParameterSpec(name=name, values=values)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-platform")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("healthcheck")
    sub.add_parser("config-validate")
    sub.add_parser("show-config")
    download = sub.add_parser("data-download")
    download.add_argument("--symbol", required=True)
    download.add_argument("--asset-class", choices=("stock", "crypto"), required=True)
    download.add_argument("--start", type=iso_date, required=True)
    download.add_argument("--end", type=iso_date, required=True)
    download.add_argument("--provider", choices=("yahoo", "coingecko"), default="yahoo")
    validate = sub.add_parser("data-validate")
    validate.add_argument("--path", type=Path, required=True)
    sub.add_parser("data-status")
    demo = sub.add_parser("data-demo")
    demo.add_argument("--symbol", default="DEMO")
    demo.add_argument("--rows", type=int, default=10)
    sub.add_parser("strategy-list")
    sub.add_parser("plugin-list")
    backtest = sub.add_parser("backtest-run")
    backtest.add_argument("--path", type=Path, required=True)
    backtest.add_argument(
        "--strategy", choices=available_strategies(), default="moving_average_cross"
    )
    backtest.add_argument("--fast", type=int, default=50)
    backtest.add_argument("--slow", type=int, default=200)
    backtest.add_argument("--initial-cash", type=float, default=None)
    backtest.add_argument("--commission", type=float, default=None)
    backtest.add_argument("--slippage-bps", type=float, default=None)
    backtest.add_argument("--report-name", default=None)

    portfolio = sub.add_parser("portfolio-backtest-run")
    portfolio.add_argument(
        "--asset",
        action="append",
        type=key_value,
        required=True,
        metavar="SYMBOL=PATH",
        help="Repeat for each asset, for example --asset SPY=data/validated/stock/SPY.parquet",
    )
    portfolio.add_argument(
        "--strategy", choices=available_strategies(), default="moving_average_cross"
    )
    portfolio.add_argument("--fast", type=int, default=50)
    portfolio.add_argument("--slow", type=int, default=200)
    portfolio.add_argument(
        "--allocation", choices=("equal", "fixed", "inverse_volatility"), default=None
    )
    portfolio.add_argument(
        "--weight", action="append", type=key_value, default=[], metavar="SYMBOL=WEIGHT"
    )
    portfolio.add_argument("--vol-lookback", type=int, default=None)
    portfolio.add_argument("--rebalance", choices=("daily", "weekly", "monthly"), default=None)
    portfolio.add_argument("--max-asset-weight", type=float, default=None)
    portfolio.add_argument("--cash-buffer-pct", type=float, default=None)
    portfolio.add_argument("--initial-cash", type=float, default=None)
    portfolio.add_argument("--commission", type=float, default=None)
    portfolio.add_argument("--slippage-bps", type=float, default=None)
    portfolio.add_argument("--report-name", default="phase4_portfolio")

    optimize = sub.add_parser("optimize-run")
    optimize.add_argument("--path", type=Path, required=True)
    optimize.add_argument(
        "--strategy", choices=available_strategies(), default="moving_average_cross"
    )
    optimize.add_argument(
        "--param", action="append", type=parameter_spec, required=True, metavar="NAME=V1,V2"
    )
    optimize.add_argument("--method", choices=("grid", "random"), default="grid")
    optimize.add_argument(
        "--objective",
        choices=("sharpe", "cagr", "sortino", "calmar", "profit_factor", "max_drawdown"),
        default="sharpe",
    )
    optimize.add_argument("--max-evaluations", type=int, default=None)
    optimize.add_argument("--seed", type=int, default=42)
    optimize.add_argument("--workers", type=int, default=1)
    optimize.add_argument("--initial-cash", type=float, default=None)
    optimize.add_argument("--commission", type=float, default=None)
    optimize.add_argument("--slippage-bps", type=float, default=None)
    optimize.add_argument("--report-name", default="phase5a_optimization")
    return parser


def _run_backtest(args: argparse.Namespace, settings_config_dir: Path, reports_dir: Path) -> int:
    bars = pd.read_parquet(args.path)
    strategy = create_strategy(args.strategy, fast_period=args.fast, slow_period=args.slow)
    config_payload = load_yaml(settings_config_dir / "backtest.yaml")
    engine_config = config_payload["engine"]
    config = BacktestConfig(
        initial_cash=float(args.initial_cash or engine_config["initial_cash"]),
        commission_per_trade=float(
            engine_config["commission_per_trade"] if args.commission is None else args.commission
        ),
        slippage_bps=float(
            engine_config["slippage_bps"] if args.slippage_bps is None else args.slippage_bps
        ),
    )
    result = BacktestEngine().run(bars, strategy, config)
    report_name = args.report_name or f"{args.path.stem}_{strategy.metadata.name}"
    output_root = _resolve_report_root(
        Path(str(config_payload["outputs"]["directory"])), reports_dir
    )
    paths = write_backtest_report(result, output_root, report_name)
    print(
        json.dumps(
            {
                "strategy": strategy.metadata.name,
                "metrics": result.metrics,
                "reports": {key: str(value) for key, value in paths.items()},
            },
            indent=2,
        )
    )
    return 0


def _run_portfolio_backtest(
    args: argparse.Namespace, settings_config_dir: Path, reports_dir: Path
) -> int:
    asset_paths = dict(args.asset)
    if len(asset_paths) < 2:
        raise ValueError("Provide at least two unique --asset SYMBOL=PATH values")
    datasets = {symbol: pd.read_parquet(Path(path)) for symbol, path in asset_paths.items()}
    weights = {symbol: float(value) for symbol, value in args.weight}
    payload = load_yaml(settings_config_dir / "portfolio.yaml")
    defaults = payload["portfolio"]
    allocation = args.allocation or str(defaults["allocation_method"])
    config = PortfolioBacktestConfig(
        initial_cash=float(args.initial_cash or defaults["initial_cash"]),
        commission_per_order=float(
            defaults["commission_per_order"] if args.commission is None else args.commission
        ),
        slippage_bps=float(
            defaults["slippage_bps"] if args.slippage_bps is None else args.slippage_bps
        ),
        allocation_method=cast(AllocationMethod, allocation),
        fixed_weights=weights,
        volatility_lookback=int(args.vol_lookback or defaults["volatility_lookback"]),
        rebalance_frequency=cast(
            RebalanceFrequency, args.rebalance or str(defaults["rebalance_frequency"])
        ),
        max_asset_weight=float(args.max_asset_weight or defaults["max_asset_weight"]),
        cash_buffer_pct=float(
            defaults["cash_buffer_pct"] if args.cash_buffer_pct is None else args.cash_buffer_pct
        ),
    )
    strategy = create_strategy(args.strategy, fast_period=args.fast, slow_period=args.slow)
    result = PortfolioBacktestEngine().run(datasets, strategy, config)
    output_root = _resolve_report_root(Path(str(payload["outputs"]["directory"])), reports_dir)
    paths = write_portfolio_report(result, output_root, args.report_name)
    print(
        json.dumps(
            {
                "strategy": strategy.metadata.name,
                "assets": sorted(asset_paths),
                "allocation": config.allocation_method,
                "metrics": result.metrics,
                "reports": {key: str(value) for key, value in paths.items()},
            },
            indent=2,
        )
    )
    return 0


def _run_optimization(
    args: argparse.Namespace, settings_config_dir: Path, reports_dir: Path
) -> int:
    bars = pd.read_parquet(args.path)
    payload = load_yaml(settings_config_dir / "research.yaml")
    defaults = payload["optimization"]
    config = OptimizationConfig(
        strategy=args.strategy,
        parameters=tuple(args.param),
        method=args.method,
        objective=args.objective,
        max_evaluations=args.max_evaluations,
        seed=args.seed,
        workers=args.workers,
        initial_cash=float(args.initial_cash or defaults["initial_cash"]),
        commission_per_trade=float(
            defaults["commission_per_trade"] if args.commission is None else args.commission
        ),
        slippage_bps=float(
            defaults["slippage_bps"] if args.slippage_bps is None else args.slippage_bps
        ),
    )
    result = OptimizationEngine().run(bars, config)
    output_root = _resolve_report_root(Path(str(payload["outputs"]["directory"])), reports_dir)
    paths = write_optimization_report(result, output_root, args.report_name)
    best = result.trials[0]
    print(
        json.dumps(
            {
                "strategy": config.strategy,
                "method": config.method,
                "objective": config.objective,
                "evaluations": len(result.trials),
                "best_parameters": best.parameters,
                "best_score": best.score,
                "best_metrics": best.metrics,
                "reports": {key: str(value) for key, value in paths.items()},
            },
            indent=2,
        )
    )
    return 0


def _resolve_report_root(configured: Path, reports_dir: Path) -> Path:
    if not configured.is_absolute() and configured.parts and configured.parts[0] == "reports":
        return reports_dir / Path(*configured.parts[1:])
    return configured


def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_logging(settings.log_level, settings.logs_dir)
    runtime = build_runtime(settings)
    context = ExecutionContext.create(args.command, settings.app_env)
    if args.command == "healthcheck":
        print(json.dumps(collect_health(settings), indent=2))
        return 0
    configs = validate_all_configs(settings.config_dir)
    if args.command == "config-validate":
        print(f"Configuration validation passed: {len(configs)} files")
        return 0
    if args.command == "show-config":
        print(json.dumps(configs, indent=2))
        return 0
    if args.command == "strategy-list":
        print(json.dumps(available_strategies(), indent=2))
        return 0
    if args.command == "plugin-list":
        print(
            json.dumps(
                [
                    {
                        "name": item.name,
                        "type": item.plugin_type.value,
                        "version": item.version,
                        "enabled": item.enabled,
                        "description": item.description,
                    }
                    for item in runtime.plugins.list()
                ],
                indent=2,
            )
        )
        return 0
    if args.command == "backtest-run":
        code = _run_backtest(args, settings.config_dir, settings.reports_dir)
        runtime.events.publish(BacktestCompleted(run_id=context.run_id, strategy=args.strategy))
        return code
    if args.command == "portfolio-backtest-run":
        code = _run_portfolio_backtest(args, settings.config_dir, settings.reports_dir)
        runtime.events.publish(BacktestCompleted(run_id=context.run_id, strategy=args.strategy))
        return code
    if args.command == "optimize-run":
        return _run_optimization(args, settings.config_dir, settings.reports_dir)
    data_config = load_yaml(settings.config_dir / "data_sources.yaml")
    storage_config = data_config["storage"]
    validated_root = Path(str(storage_config["validated_directory"]))
    service = MarketDataService(data_config, validated_root)
    if args.command == "data-download":
        if args.end < args.start:
            raise ValueError("--end cannot be before --start")
        path, report = service.download(
            args.symbol, args.asset_class, args.start, args.end, args.provider
        )
        runtime.events.publish(
            MarketDataLoaded(
                run_id=context.run_id,
                symbols=(args.symbol.upper(),),
                rows=report.rows,
            )
        )
        print(json.dumps({"path": str(path), "quality": report.to_dict()}, indent=2))
        return 0
    if args.command == "data-validate":
        report = service.validate_file(args.path)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed else 1
    if args.command == "data-status":
        print(json.dumps(build_catalog(validated_root), indent=2))
        return 0
    if args.command == "data-demo":
        if args.rows <= 0:
            raise ValueError("--rows must be positive")
        store = ParquetBarStore(validated_root, str(storage_config.get("compression", "snappy")))
        path = store.write(make_demo_bars(args.symbol, rows=args.rows), "stock", args.symbol)
        print(json.dumps({"path": str(path), "mode": "offline-demo"}, indent=2))
        return 0
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = run(args)
    except (QuantPlatformError, OSError, ValueError) as exc:
        LOGGER.error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
