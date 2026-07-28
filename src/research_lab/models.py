from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestSettings:
    initial_capital: float = 100_000.0
    allocation_fraction: float = 1.0
    commission_per_order: float = 0.0
    slippage_bps: float = 2.0

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.allocation_fraction <= 1:
            raise ValueError("allocation_fraction must be in (0, 1]")
        if self.commission_per_order < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")


@dataclass(frozen=True)
class StrategyBacktestResult:
    strategy: str
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    maximum_drawdown: float
    win_rate: float
    profit_factor: float
    trade_count: int
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    trades: pd.DataFrame


@dataclass(frozen=True)
class ComparisonResult:
    results: tuple[StrategyBacktestResult, ...]

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Strategy": item.strategy,
                    "Final Equity": item.final_equity,
                    "Total Return": item.total_return,
                    "Annualized Return": item.annualized_return,
                    "Maximum Drawdown": item.maximum_drawdown,
                    "Sharpe": item.sharpe_ratio,
                    "Win Rate": item.win_rate,
                    "Profit Factor": item.profit_factor,
                    "Trades": item.trade_count,
                }
                for item in self.results
            ]
        ).sort_values(["Sharpe", "Total Return"], ascending=False, ignore_index=True)
