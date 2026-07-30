from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from src.rotation_engine.engine import RotationBacktestEngine
from src.rotation_engine.models import AssetClass, RotationBacktestResult, RotationConfig

STABLECOIN_TOKENS = {
    "dai",
    "ethena-usde",
    "global-dollar",
    "paypal-usd",
    "tether",
    "usd-coin",
    "usd1-wlfi",
    "usdd",
}


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported file type: {path}")


def _parse_asset(path: Path) -> tuple[str, AssetClass]:
    parent = path.parent.name.lower()
    stem = path.stem

    if parent in {"stock", "stocks"}:
        asset_class = AssetClass.STOCK
    elif parent in {"etf", "etfs"}:
        asset_class = AssetClass.ETF
    elif parent in {"crypto", "cryptos"}:
        asset_class = AssetClass.CRYPTO
    elif stem.startswith("stock__"):
        asset_class = AssetClass.STOCK
    elif stem.startswith("etf__"):
        asset_class = AssetClass.ETF
    elif stem.startswith("crypto__"):
        asset_class = AssetClass.CRYPTO
    else:
        raise ValueError("cannot infer asset class")

    symbol = stem
    for prefix in ("stock__", "etf__", "crypto__"):
        if symbol.startswith(prefix):
            symbol = symbol[len(prefix) :]
            break

    symbol = symbol.removesuffix("_2024").removesuffix("_2025")
    return symbol.upper(), asset_class


def _eligible_rows(
    frame: pd.DataFrame,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    minimum_history_bars: int,
    minimum_test_bars: int,
) -> bool:
    bars = frame.copy()
    if "timestamp" in bars.columns:
        index = pd.to_datetime(bars["timestamp"], utc=True)
    else:
        index = pd.to_datetime(bars.index, utc=True)

    history_count = int((index < test_start).sum())
    test_count = int(((index >= test_start) & (index <= test_end)).sum())
    return history_count >= minimum_history_bars and test_count >= minimum_test_bars


def _discover(
    asset_dir: Path,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    minimum_history_bars: int,
    minimum_test_bars: int,
    exclude_stablecoins: bool,
    maximum_assets: int | None,
) -> tuple[dict[str, pd.DataFrame], dict[str, AssetClass], list[dict[str, str]]]:
    paths = sorted(
        [
            *asset_dir.rglob("*.parquet"),
            *asset_dir.rglob("*.csv"),
        ]
    )
    datasets: dict[str, pd.DataFrame] = {}
    asset_classes: dict[str, AssetClass] = {}
    skipped: list[dict[str, str]] = []

    for path in paths:
        if maximum_assets is not None and len(datasets) >= maximum_assets:
            break

        try:
            symbol, asset_class = _parse_asset(path)
            if (
                exclude_stablecoins
                and asset_class == AssetClass.CRYPTO
                and symbol.lower() in STABLECOIN_TOKENS
            ):
                skipped.append({"path": str(path), "reason": "stablecoin"})
                continue

            frame = _read_frame(path)
            if not _eligible_rows(
                frame,
                test_start,
                test_end,
                minimum_history_bars,
                minimum_test_bars,
            ):
                skipped.append(
                    {
                        "path": str(path),
                        "reason": "insufficient_history_or_test_rows",
                    }
                )
                continue

            if symbol in datasets:
                skipped.append({"path": str(path), "reason": "duplicate_symbol"})
                continue

            datasets[symbol] = frame
            asset_classes[symbol] = asset_class
        except Exception as exc:
            skipped.append({"path": str(path), "reason": str(exc)})

    if not datasets:
        raise ValueError("no eligible assets were discovered")
    return datasets, asset_classes, skipped


def _write_reports(
    result: RotationBacktestResult,
    output_dir: Path,
    skipped: list[dict[str, str]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(dict(result.metrics), indent=2),
        encoding="utf-8",
    )

    trades = pd.DataFrame(
        [
            {
                **asdict(trade),
                "asset_class": trade.asset_class.value,
                "exit_reason": trade.exit_reason.value,
            }
            for trade in result.trades
        ]
    )
    trades_path = output_dir / "trades.csv"
    trades.to_csv(trades_path, index=False)

    equity = pd.DataFrame(
        result.equity_curve,
        columns=["timestamp", "equity"],
    )
    equity_path = output_dir / "equity.csv"
    equity.to_csv(equity_path, index=False)

    decisions_path = output_dir / "decisions.json"
    decisions_path.write_text(
        json.dumps(list(result.decisions), indent=2, default=str),
        encoding="utf-8",
    )

    skipped_path = output_dir / "skipped_assets.csv"
    pd.DataFrame(skipped).to_csv(skipped_path, index=False)

    if trades.empty:
        symbol_attribution = pd.DataFrame()
        strategy_attribution = pd.DataFrame()
    else:
        symbol_attribution = _attribution(trades, "symbol")
        strategy_attribution = _attribution(trades, "strategy")

    symbol_path = output_dir / "symbol_attribution.csv"
    symbol_attribution.to_csv(symbol_path, index=False)

    strategy_path = output_dir / "strategy_attribution.csv"
    strategy_attribution.to_csv(strategy_path, index=False)

    monthly_path = output_dir / "monthly_returns.csv"
    yearly_path = output_dir / "yearly_returns.csv"
    _period_returns(equity, "M").to_csv(monthly_path, index=False)
    _period_returns(equity, "Y").to_csv(yearly_path, index=False)

    return {
        "metrics": str(metrics_path),
        "trades": str(trades_path),
        "equity": str(equity_path),
        "decisions": str(decisions_path),
        "skipped_assets": str(skipped_path),
        "symbol_attribution": str(symbol_path),
        "strategy_attribution": str(strategy_path),
        "monthly_returns": str(monthly_path),
        "yearly_returns": str(yearly_path),
    }


def _attribution(trades: pd.DataFrame, key: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value, group in trades.groupby(key, dropna=False):
        wins = group[group["net_pnl"] > 0]
        losses = group[group["net_pnl"] < 0]
        gross_profit = float(wins["net_pnl"].sum())
        gross_loss = abs(float(losses["net_pnl"].sum()))
        rows.append(
            {
                key: value,
                "trades": len(group),
                "wins": len(wins),
                "win_rate": len(wins) / len(group),
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "net_pnl": float(group["net_pnl"].sum()),
                "profit_factor": (gross_profit / gross_loss if gross_loss > 0 else float("inf")),
                "average_pnl": float(group["net_pnl"].mean()),
                "average_holding_days": float(group["holding_days"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("net_pnl", ascending=False)


def _period_returns(equity: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame(columns=["period", "return"])

    data = equity.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    data = data.set_index("timestamp").sort_index()
    grouped = data["equity"].resample(frequency).agg(["first", "last"]).dropna()
    grouped["return"] = grouped["last"] / grouped["first"] - 1.0
    grouped = grouped.reset_index()
    grouped["period"] = grouped["timestamp"].dt.strftime("%Y-%m" if frequency == "M" else "%Y")
    return grouped[["period", "return"]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run rotation backtest over all eligible assets in a directory."
    )
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--test-start", required=True)
    parser.add_argument("--test-end", required=True)
    parser.add_argument("--minimum-history-bars", type=int, default=65)
    parser.add_argument("--minimum-test-bars", type=int, default=200)
    parser.add_argument("--exclude-stablecoins", action="store_true")
    parser.add_argument("--maximum-assets", type=int)
    parser.add_argument("--initial-cash", type=float, default=5000.0)
    parser.add_argument("--max-positions", type=int, default=4)
    parser.add_argument("--min-hold-days", type=int, default=1)
    parser.add_argument("--preferred-max-hold-days", type=int, default=10)
    parser.add_argument("--max-hold-days", type=int, default=30)
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.5)
    parser.add_argument("--max-position-pct", type=float, default=25.0)
    parser.add_argument("--max-crypto-position-pct", type=float, default=12.0)
    parser.add_argument("--total-crypto-pct", type=float, default=25.0)
    parser.add_argument("--cash-reserve-pct", type=float, default=10.0)
    parser.add_argument("--min-entry-score", type=float, default=62.0)
    parser.add_argument("--rotation-score-improvement", type=float, default=12.0)
    parser.add_argument("--report-name", required=True)
    return parser


def _pct(value: float) -> float:
    return value / 100.0 if value > 1.0 else value


def main() -> None:
    args = build_parser().parse_args()
    test_start = pd.Timestamp(args.test_start)
    test_end = pd.Timestamp(args.test_end)
    if test_start.tzinfo is None:
        test_start = test_start.tz_localize("UTC")
    else:
        test_start = test_start.tz_convert("UTC")
    if test_end.tzinfo is None:
        test_end = test_end.tz_localize("UTC")
    else:
        test_end = test_end.tz_convert("UTC")

    datasets, asset_classes, skipped = _discover(
        args.asset_dir,
        test_start,
        test_end,
        args.minimum_history_bars,
        args.minimum_test_bars,
        args.exclude_stablecoins,
        args.maximum_assets,
    )

    config = RotationConfig(
        initial_cash=args.initial_cash,
        max_positions=args.max_positions,
        min_hold_days=args.min_hold_days,
        preferred_max_hold_days=args.preferred_max_hold_days,
        max_hold_days=args.max_hold_days,
        risk_per_trade_pct=_pct(args.risk_per_trade_pct),
        max_position_pct=_pct(args.max_position_pct),
        max_crypto_position_pct=_pct(args.max_crypto_position_pct),
        total_crypto_pct=_pct(args.total_crypto_pct),
        cash_reserve_pct=_pct(args.cash_reserve_pct),
        min_entry_score=_pct(args.min_entry_score),
        rotation_score_improvement=_pct(args.rotation_score_improvement),
    )

    result = RotationBacktestEngine().run(
        datasets,
        asset_classes,
        config,
        test_start=test_start,
        test_end=test_end,
    )
    output_dir = Path("reports") / "rotation" / args.report_name
    reports = _write_reports(result, output_dir, skipped)

    payload = {
        "asset_count": len(datasets),
        "skipped_count": len(skipped),
        "assets": sorted(datasets),
        "metrics": dict(result.metrics),
        "reports": reports,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
