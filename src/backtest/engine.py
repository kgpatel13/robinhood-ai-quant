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

        for position, (_, row) in enumerate(ordered.iterrows()):
            target = float(targets.iloc[position])
            open_price = float(row["open"])
            if target > 0.0 and previous_target == 0.0:
                fill = open_price * (1.0 + slippage)
                available = max(cash - config.commission_per_trade, 0.0)
                quantity = available / fill
                entry_cost = quantity * fill + config.commission_per_trade
                cash -= entry_cost
                trades.append(
                    {
                        "timestamp": row["timestamp"],
                        "side": "BUY",
                        "price": fill,
                        "quantity": quantity,
                        "commission": config.commission_per_trade,
                        "realized_pnl": 0.0,
                    }
                )
            elif target == 0.0 and previous_target > 0.0 and quantity > 0.0:
                fill = open_price * (1.0 - slippage)
                proceeds = quantity * fill - config.commission_per_trade
                realized = proceeds - entry_cost
                cash += proceeds
                trades.append(
                    {
                        "timestamp": row["timestamp"],
                        "side": "SELL",
                        "price": fill,
                        "quantity": quantity,
                        "commission": config.commission_per_trade,
                        "realized_pnl": realized,
                    }
                )
                quantity = 0.0
                entry_cost = 0.0
            equity = cash + quantity * float(row["close"])
            curve.append(
                {
                    "timestamp": row["timestamp"],
                    "close": float(row["close"]),
                    "target": target,
                    "cash": cash,
                    "quantity": quantity,
                    "equity": equity,
                }
            )
            previous_target = target

        equity_curve = pd.DataFrame(curve)
        trade_frame = pd.DataFrame(
            trades,
            columns=["timestamp", "side", "price", "quantity", "commission", "realized_pnl"],
        )
        metrics = calculate_metrics(equity_curve, trade_frame)
        return BacktestResult(equity_curve, trade_frame, metrics)
