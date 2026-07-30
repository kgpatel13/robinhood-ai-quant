from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.rotation_engine.models import RotationBacktestResult


def _trade_frame(result: RotationBacktestResult) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(trade) for trade in result.trades])
    if frame.empty:
        return frame
    frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    return frame


def _attribution(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                column,
                "trades",
                "wins",
                "win_rate",
                "gross_profit",
                "gross_loss",
                "net_pnl",
                "profit_factor",
                "average_pnl",
                "average_holding_days",
                "total_costs",
            ]
        )

    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(column, dropna=False):
        wins = group[group["net_pnl"] > 0]
        losses = group[group["net_pnl"] < 0]
        gross_profit = float(wins["net_pnl"].sum())
        gross_loss = abs(float(losses["net_pnl"].sum()))
        rows.append(
            {
                column: key,
                "trades": len(group),
                "wins": len(wins),
                "win_rate": len(wins) / len(group),
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "net_pnl": float(group["net_pnl"].sum()),
                "profit_factor": (
                    gross_profit / gross_loss
                    if gross_loss > 0
                    else (float("inf") if gross_profit > 0 else 0.0)
                ),
                "average_pnl": float(group["net_pnl"].mean()),
                "average_holding_days": float(group["holding_days"].mean()),
                "total_costs": float(group["costs"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("net_pnl", ascending=False)


def _period_returns(equity: pd.DataFrame, frequency: str, label: str) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame(columns=[label, "start_equity", "end_equity", "return"])

    indexed = equity.set_index("timestamp")["equity"].sort_index()
    grouped = indexed.resample(frequency)
    rows: list[dict[str, Any]] = []
    for period_key, values in grouped:
        if values.empty:
            continue
        period = cast(pd.Timestamp, period_key)
        start = float(values.iloc[0])
        end = float(values.iloc[-1])
        rows.append(
            {
                label: period.strftime("%Y-%m" if frequency == "ME" else "%Y"),
                "start_equity": start,
                "end_equity": end,
                "return": end / start - 1.0 if start else 0.0,
            }
        )
    return pd.DataFrame(rows)


def write_rotation_report(
    result: RotationBacktestResult, output_dir: Path, report_name: str
) -> dict[str, Path]:
    root = output_dir / report_name
    root.mkdir(parents=True, exist_ok=True)

    metrics_path = root / "metrics.json"
    trades_path = root / "trades.csv"
    equity_path = root / "equity.csv"
    decisions_path = root / "decisions.json"
    symbol_path = root / "symbol_attribution.csv"
    strategy_path = root / "strategy_attribution.csv"
    monthly_path = root / "monthly_returns.csv"
    yearly_path = root / "yearly_returns.csv"

    metrics_path.write_text(json.dumps(dict(result.metrics), indent=2), encoding="utf-8")

    trades = _trade_frame(result)
    trades.to_csv(trades_path, index=False)

    equity = pd.DataFrame(result.equity_curve, columns=["timestamp", "equity"])
    if not equity.empty:
        equity["timestamp"] = pd.to_datetime(equity["timestamp"], utc=True)
    equity.to_csv(equity_path, index=False)

    decisions_path.write_text(
        json.dumps(list(result.decisions), indent=2, default=str), encoding="utf-8"
    )

    _attribution(trades, "symbol").to_csv(symbol_path, index=False)
    _attribution(trades, "strategy").to_csv(strategy_path, index=False)
    _period_returns(equity, "ME", "month").to_csv(monthly_path, index=False)
    _period_returns(equity, "YE", "year").to_csv(yearly_path, index=False)

    return {
        "metrics": metrics_path,
        "trades": trades_path,
        "equity": equity_path,
        "decisions": decisions_path,
        "symbol_attribution": symbol_path,
        "strategy_attribution": strategy_path,
        "monthly_returns": monthly_path,
        "yearly_returns": yearly_path,
    }
