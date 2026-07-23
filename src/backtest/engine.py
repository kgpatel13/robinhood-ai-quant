from __future__ import annotations

from typing import Any

import pandas as pd

from src.analytics.performance import calculate_metrics
from src.backtest.models import BacktestConfig, BacktestResult
from src.strategies.base import Strategy


class BacktestEngine:
    def run(self, bars: pd.DataFrame, strategy: Strategy, config: BacktestConfig) -> BacktestResult:
        if len(bars) < strategy.metadata.required_history + 2:
            raise ValueError(
                f"Strategy requires at least {strategy.metadata.required_history + 2} rows"
            )
        ordered = bars.sort_values("timestamp").reset_index(drop=True).copy()
        signals = strategy.generate_signals(ordered).clip(0.0, 1.0)
        # Shift one bar: signals computed at close are executed at the next open.
        targets = signals.shift(1).fillna(0.0)
        cash = config.initial_cash
        quantity = 0.0
        entry_cost = 0.0
        trades: list[dict[str, Any]] = []
        curve: list[dict[str, Any]] = []
        previous_target = 0.0
        slippage = config.slippage_bps / 10_000.0
        fee_rate = config.fee_bps / 10_000.0
        entry_timestamp: object | None = None
        entry_price = 0.0

        for position, (_, row) in enumerate(ordered.iterrows()):
            target = float(targets.iloc[position])
            open_price = float(row["open"])
            if target > 0.0 and previous_target == 0.0:
                fill = open_price * (1.0 + slippage)
                quantity = max(cash - config.commission_per_trade, 0.0) / (fill * (1.0 + fee_rate))
                fee = quantity * fill * fee_rate
                entry_cost = quantity * fill + fee + config.commission_per_trade
                cash -= entry_cost
                trades.append(
                    {
                        "timestamp": row["timestamp"],
                        "side": "BUY",
                        "price": fill,
                        "quantity": quantity,
                        "commission": config.commission_per_trade,
                        "fee": fee,
                        "realized_pnl": 0.0,
                        "holding_days": 0,
                    }
                )
                entry_timestamp = row["timestamp"]
                entry_price = fill
            elif target == 0.0 and previous_target > 0.0 and quantity > 0.0:
                fill = open_price * (1.0 - slippage)
                fee = quantity * fill * fee_rate
                proceeds = quantity * fill - fee - config.commission_per_trade
                realized = proceeds - entry_cost
                holding_days = (
                    (row["timestamp"] - entry_timestamp).days if entry_timestamp is not None else 0
                )
                cash += proceeds
                trades.append(
                    {
                        "timestamp": row["timestamp"],
                        "side": "SELL",
                        "price": fill,
                        "quantity": quantity,
                        "commission": config.commission_per_trade,
                        "fee": fee,
                        "realized_pnl": realized,
                        "holding_days": holding_days,
                        "entry_price": entry_price,
                    }
                )
                quantity = 0.0
                entry_cost = 0.0
                entry_timestamp = None
                entry_price = 0.0
            equity = cash + quantity * float(row["close"])
            curve.append(
                {
                    "timestamp": row["timestamp"],
                    "close": float(row["close"]),
                    "target": target,
                    "cash": cash,
                    "quantity": quantity,
                    "equity": equity,
                    "unrealized_pnl": (
                        quantity * float(row["close"]) - entry_cost if quantity > 0 else 0.0
                    ),
                }
            )
            previous_target = target

        equity_curve = pd.DataFrame(curve)
        trade_frame = pd.DataFrame(
            trades,
            columns=[
                "timestamp",
                "side",
                "price",
                "quantity",
                "commission",
                "fee",
                "realized_pnl",
                "holding_days",
                "entry_price",
            ],
        )
        metrics = calculate_metrics(equity_curve, trade_frame)
        return BacktestResult(equity_curve, trade_frame, metrics)
