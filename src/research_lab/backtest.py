from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

from src.research_lab.models import BacktestSettings, ComparisonResult, StrategyBacktestResult
from src.strategies.base import Strategy
from src.strategies.registry import create_strategy


class StrategyBacktestEngine:
    def __init__(self, settings: BacktestSettings | None = None) -> None:
        self.settings = settings or BacktestSettings()

    def run(self, bars: pd.DataFrame, strategy: Strategy) -> StrategyBacktestResult:
        signals = strategy.generate_signals(bars).reindex(bars.index).fillna(0.0).clip(0.0, 1.0)
        exposure = signals.shift(1).fillna(0.0) * self.settings.allocation_fraction
        asset_returns = bars["close"].astype(float).pct_change().fillna(0.0)
        turnover = exposure.diff().abs().fillna(exposure.abs())
        costs = turnover * self.settings.slippage_bps / 10_000
        order_cost = (
            turnover.gt(0).astype(float)
            * self.settings.commission_per_order
            / self.settings.initial_capital
        )
        returns = exposure * asset_returns - costs - order_cost
        equity = self.settings.initial_capital * (1.0 + returns).cumprod()
        peaks = equity.cummax()
        drawdown = equity / peaks - 1.0
        trades = self._trade_ledger(bars, signals)
        wins = trades.loc[trades["pnl"] > 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
        losses = (
            trades.loc[trades["pnl"] < 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
        )
        annualized_return = self._annualized_return(equity)
        volatility = float(returns.std(ddof=0) * math.sqrt(252))
        return_std = float(returns.std(ddof=0))
        sharpe = float(returns.mean() / return_std * math.sqrt(252)) if return_std > 0 else 0.0
        if not losses.empty and float(losses.sum()) != 0.0:
            profit_factor = float(wins.sum() / abs(float(losses.sum())))
        else:
            profit_factor = float("inf") if not wins.empty else 0.0
        return StrategyBacktestResult(
            strategy=strategy.plugin_name,
            initial_capital=self.settings.initial_capital,
            final_equity=float(equity.iloc[-1]),
            total_return=float(equity.iloc[-1] / self.settings.initial_capital - 1.0),
            annualized_return=annualized_return,
            annualized_volatility=volatility,
            sharpe_ratio=sharpe,
            maximum_drawdown=float(drawdown.min()),
            win_rate=float((trades["pnl"] > 0).mean()) if not trades.empty else 0.0,
            profit_factor=profit_factor,
            trade_count=len(trades),
            equity_curve=equity.rename(strategy.plugin_name),
            drawdown_curve=drawdown.rename(strategy.plugin_name),
            trades=trades,
        )

    def compare(self, bars: pd.DataFrame, strategy_names: Iterable[str]) -> ComparisonResult:
        results = tuple(self.run(bars, create_strategy(name)) for name in strategy_names)
        return ComparisonResult(results)

    @staticmethod
    def _annualized_return(equity: pd.Series) -> float:
        periods = max(len(equity) - 1, 1)
        years = periods / 252.0
        if years <= 0:
            return 0.0
        return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)

    def _trade_ledger(self, bars: pd.DataFrame, signals: pd.Series) -> pd.DataFrame:
        records: list[dict[str, object]] = []
        entry_time: pd.Timestamp | None = None
        entry_price = 0.0
        previous = 0.0
        for index in range(len(signals)):
            timestamp = pd.Timestamp(signals.index[index])
            current = float(signals.iloc[index])
            price = float(bars["close"].iloc[index])
            if current > 0 and previous <= 0:
                entry_time = pd.Timestamp(timestamp)
                entry_price = price * (1 + self.settings.slippage_bps / 10_000)
            elif current <= 0 and previous > 0 and entry_time is not None:
                exit_price = price * (1 - self.settings.slippage_bps / 10_000)
                records.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": timestamp,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": exit_price / entry_price - 1.0,
                    }
                )
                entry_time = None
            previous = current
        if previous > 0 and entry_time is not None:
            timestamp = pd.Timestamp(bars.index[-1])
            exit_price = float(bars["close"].iloc[-1]) * (1 - self.settings.slippage_bps / 10_000)
            records.append(
                {
                    "entry_time": entry_time,
                    "exit_time": timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": exit_price / entry_price - 1.0,
                }
            )
        return pd.DataFrame.from_records(
            records,
            columns=["entry_time", "exit_time", "entry_price", "exit_price", "pnl"],
        )
