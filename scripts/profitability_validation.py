from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest.engine import BacktestEngine  # noqa: E402
from src.backtest.models import BacktestConfig  # noqa: E402
from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter  # noqa: E402
from src.strategies.registry import (  # noqa: E402
    available_strategies,
    create_strategy,
    strategy_defaults,
)

DEFAULT_SYMBOLS = ("SPY", "QQQ", "VTI", "AAPL", "MSFT", "NVDA")
DEFAULT_YEARS = (1, 3, 5)


class BuyAndHoldStrategy(Strategy):
    plugin_name = "buy_and_hold"

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name=self.plugin_name,
            description="Buy at the first executable bar and hold",
            required_history=1,
            category="benchmark",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return ()

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {}

    def validate_parameters(self) -> None:
        return None

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=bars.index, dtype=float)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate historical profitability using the existing backtest engine."
    )
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--fee-bps", type=float, default=0.0)
    parser.add_argument("--commission", type=float, default=0.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports") / "profitability_validation",
    )
    return parser.parse_args()


def _normalize_ohlcv(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    result = frame.copy()
    if "timestamp" not in result.columns:
        raise ValueError(f"{symbol}: missing timestamp column")
    if "close" not in result.columns:
        raise ValueError(f"{symbol}: missing close column")

    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    for column in ("open", "high", "low"):
        if column not in result.columns:
            result[column] = result["close"]
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if "volume" not in result.columns:
        result["volume"] = 0.0
    result["volume"] = pd.to_numeric(result["volume"], errors="coerce").fillna(0.0)

    return (
        result.loc[:, ["timestamp", "open", "high", "low", "close", "volume"]]
        .dropna(subset=["timestamp", "open", "high", "low", "close"])
        .sort_values("timestamp")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )


def load_symbol(project_root: Path, symbol: str) -> pd.DataFrame:
    symbol = symbol.upper()
    candidates = (
        project_root / "data" / "validated" / "etf" / f"{symbol}.parquet",
        project_root / "data" / "validated" / "stock" / f"{symbol}.parquet",
        project_root / "data" / "benchmarks" / f"{symbol}.csv",
    )
    errors: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            return _normalize_ohlcv(frame, symbol)
        except (ImportError, OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    details = "; ".join(errors) if errors else "no matching data file"
    raise FileNotFoundError(f"Unable to load {symbol}: {details}")


def select_window(frame: pd.DataFrame, years: int) -> pd.DataFrame:
    if years <= 0:
        raise ValueError("years must be positive")
    end = frame["timestamp"].max()
    start = end - pd.DateOffset(years=years)
    selected: pd.DataFrame = frame.loc[frame["timestamp"] >= start].reset_index(drop=True)
    return selected


def _strategy_map() -> dict[str, Strategy]:
    strategies: dict[str, Strategy] = {"buy_and_hold": BuyAndHoldStrategy()}
    for name in available_strategies():
        strategies[name] = create_strategy(name, **strategy_defaults(name))
    return strategies


def _verdict(row: dict[str, Any]) -> str:
    total_return = float(row["total_return"])
    sharpe = float(row["sharpe_ratio"])
    drawdown = abs(float(row["max_drawdown"]))
    if total_return > 0 and sharpe >= 0.7 and drawdown <= 0.25:
        return "PASS"
    if total_return > 0:
        return "PROMISING_BUT_UNPROVEN"
    return "FAIL"


def run_validation(args: argparse.Namespace) -> pd.DataFrame:
    project_root = PROJECT_ROOT
    output = args.output if args.output.is_absolute() else project_root / args.output
    output.mkdir(parents=True, exist_ok=True)

    config = BacktestConfig(
        initial_cash=args.capital,
        commission_per_trade=args.commission,
        slippage_bps=args.slippage_bps,
        fee_bps=args.fee_bps,
        max_exposure=1.0,
    )
    engine = BacktestEngine()
    strategies = _strategy_map()
    rows: list[dict[str, Any]] = []
    equity_series: dict[str, pd.Series] = {}
    warnings: list[str] = []

    requested_symbols = list(dict.fromkeys([*args.symbols, args.benchmark]))
    for symbol in requested_symbols:
        try:
            full_frame = load_symbol(project_root, symbol)
        except FileNotFoundError as exc:
            warnings.append(str(exc))
            continue

        for years in sorted(set(args.years)):
            bars = select_window(full_frame, years)
            if len(bars) < 3:
                warnings.append(f"{symbol}/{years}y: insufficient rows ({len(bars)})")
                continue

            for strategy_name, strategy in strategies.items():
                minimum_rows = strategy.metadata.required_history + 2
                if len(bars) < minimum_rows:
                    warnings.append(
                        f"{symbol}/{years}y/{strategy_name}: requires {minimum_rows} rows, "
                        f"found {len(bars)}"
                    )
                    continue
                try:
                    result = engine.run(bars, strategy, config)
                except (ValueError, ZeroDivisionError) as exc:
                    warnings.append(f"{symbol}/{years}y/{strategy_name}: {exc}")
                    continue

                metrics = result.metrics
                row: dict[str, Any] = {
                    "symbol": symbol,
                    "period_years": years,
                    "start": bars["timestamp"].iloc[0].date().isoformat(),
                    "end": bars["timestamp"].iloc[-1].date().isoformat(),
                    "rows": len(bars),
                    "strategy": strategy_name,
                    "initial_capital": args.capital,
                    **metrics,
                }
                row["net_profit"] = float(metrics["final_equity"]) - args.capital
                row["verdict"] = _verdict(row)
                rows.append(row)

                label = f"{symbol} {years}y {strategy_name}"
                series = result.equity_curve.set_index("timestamp")["equity"]
                equity_series[label] = series
                result.trades.to_csv(
                    output / f"trades_{symbol}_{years}y_{strategy_name}.csv",
                    index=False,
                )

    summary = pd.DataFrame(rows)
    if summary.empty:
        raise RuntimeError("No validation cases could be executed. Check historical data files.")

    summary = summary.sort_values(
        ["symbol", "period_years", "final_equity"], ascending=[True, True, False]
    ).reset_index(drop=True)
    summary.to_csv(output / "summary.csv", index=False)

    winners = (
        summary.sort_values("final_equity", ascending=False)
        .groupby(["symbol", "period_years"], as_index=False)
        .first()
    )
    winners.to_csv(output / "best_by_symbol_period.csv", index=False)

    _write_report(output, summary, winners, args, warnings)
    _write_charts(output, equity_series)
    (output / "run_metadata.json").write_text(
        json.dumps(
            {
                "capital": args.capital,
                "years": sorted(set(args.years)),
                "symbols": requested_symbols,
                "benchmark": args.benchmark,
                "slippage_bps": args.slippage_bps,
                "fee_bps": args.fee_bps,
                "commission": args.commission,
                "warnings": warnings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary


def _write_charts(output: Path, equity_series: dict[str, pd.Series]) -> None:
    if not equity_series:
        return
    for label, series in equity_series.items():
        safe = label.lower().replace(" ", "_")
        figure, axis = plt.subplots(figsize=(10, 5))
        values = series.to_numpy(dtype=float)
        axis.plot(series.index, values)
        axis.set_title(label)
        axis.set_xlabel("Date")
        axis.set_ylabel("Portfolio value ($)")
        axis.grid(True, alpha=0.25)
        figure.tight_layout()
        figure.savefig(output / f"equity_{safe}.png", dpi=140)
        plt.close(figure)


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _money(value: Any) -> str:
    return f"${float(value):,.2f}"


def _write_report(
    output: Path,
    summary: pd.DataFrame,
    winners: pd.DataFrame,
    args: argparse.Namespace,
    warnings: list[str],
) -> None:
    lines = [
        "# Historical Profitability Validation",
        "",
        f"Initial capital: **{_money(args.capital)}**",
        f"Slippage: **{args.slippage_bps:.2f} bps per side**",
        f"Commission: **{_money(args.commission)} per trade**",
        "",
        "## Best result by symbol and period",
        "",
        (
            "| Symbol | Period | Strategy | Final value | Return | CAGR | "
            "Max drawdown | Sharpe | Trades | Verdict |"
        ),
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in winners.sort_values(["symbol", "period_years"]).iterrows():
        lines.append(
            "| "
            f"{row['symbol']} | {int(row['period_years'])}y | {row['strategy']} | "
            f"{_money(row['final_equity'])} | {_percent(row['total_return'])} | "
            f"{_percent(row['cagr'])} | {_percent(row['max_drawdown'])} | "
            f"{float(row['sharpe_ratio']):.2f} | {int(row['trade_count'])} | "
            f"{row['verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report is a historical simulation, not a guarantee of future profit. "
            "Results should be compared with buy-and-hold for the same symbol, tested "
            "out-of-sample, and stress-tested with higher costs before capital is deployed.",
        ]
    )
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    (output / "profitability_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_console_summary(summary: pd.DataFrame) -> None:
    winners = (
        summary.sort_values("final_equity", ascending=False)
        .groupby(["symbol", "period_years"], as_index=False)
        .first()
        .sort_values(["symbol", "period_years"])
    )
    columns = [
        "symbol",
        "period_years",
        "strategy",
        "initial_capital",
        "final_equity",
        "total_return",
        "max_drawdown",
        "sharpe_ratio",
        "trade_count",
        "verdict",
    ]
    display = winners.loc[:, columns].copy()
    display["initial_capital"] = display["initial_capital"].map(_money)
    display["final_equity"] = display["final_equity"].map(_money)
    display["total_return"] = display["total_return"].map(_percent)
    display["max_drawdown"] = display["max_drawdown"].map(_percent)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(lambda value: f"{value:.2f}")
    print("\nBest historical result by symbol and period:\n")
    print(display.to_string(index=False))


def main() -> int:
    args = parse_args()
    if args.capital <= 0:
        raise SystemExit("--capital must be positive")
    if any(year <= 0 for year in args.years):
        raise SystemExit("--years values must be positive")
    summary = run_validation(args)
    print_console_summary(summary)
    project_root = PROJECT_ROOT
    output = args.output if args.output.is_absolute() else project_root / args.output
    print(f"\nReports written to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
