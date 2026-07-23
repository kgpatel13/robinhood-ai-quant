from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from src.backtest import BacktestConfig, BacktestEngine
from src.common.config import load_settings, load_yaml, validate_all_configs
from src.common.exceptions import QuantPlatformError
from src.common.health import collect_health
from src.common.logging_config import configure_logging
from src.data.catalog import build_catalog
from src.data.demo import make_demo_bars
from src.data.service import MarketDataService
from src.data.storage import ParquetBarStore
from src.reporting import write_backtest_report
from src.strategies import available_strategies, create_strategy

LOGGER = logging.getLogger(__name__)


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD") from exc


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
    output_root = Path(str(config_payload["outputs"]["directory"]))
    if not output_root.is_absolute() and output_root.parts[0] == "reports":
        output_root = reports_dir / Path(*output_root.parts[1:])
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


def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_logging(settings.log_level, settings.logs_dir)
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
    if args.command == "backtest-run":
        return _run_backtest(args, settings.config_dir, settings.reports_dir)
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
