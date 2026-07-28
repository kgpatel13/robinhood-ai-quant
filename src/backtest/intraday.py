from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd

from src.strategies.intraday import IntradayMomentumStrategy, IntradaySignal


@dataclass(frozen=True)
class IntradayBacktestConfig:
    initial_capital: float = 10_000.0
    position_fraction: float = 0.25
    commission_per_order: float = 0.0
    slippage_bps: float = 2.0
    liquidation_time: time = time(15, 55)

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction must be in (0, 1]")
        if self.commission_per_order < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")


@dataclass(frozen=True)
class IntradayTrade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float


@dataclass(frozen=True)
class IntradayBacktestResult:
    initial_capital: float
    final_equity: float
    total_return: float
    trade_count: int
    forced_liquidations: int
    trades: tuple[IntradayTrade, ...]


class IntradayBacktestEngine:
    def __init__(
        self,
        strategy: IntradayMomentumStrategy | None = None,
        config: IntradayBacktestConfig | None = None,
    ) -> None:
        self.strategy = strategy or IntradayMomentumStrategy()
        self.config = config or IntradayBacktestConfig()

    def run(self, bars: pd.DataFrame) -> IntradayBacktestResult:
        cash = self.config.initial_capital
        quantity = 0.0
        entry_price = 0.0
        entry_time: pd.Timestamp | None = None
        trades: list[IntradayTrade] = []
        forced = 0
        for index in range(len(bars)):
            timestamp = pd.Timestamp(bars.index[index])
            price = float(bars["close"].iloc[index])
            assessment = self.strategy.assess(bars.iloc[: index + 1])
            should_exit = quantity > 0 and (
                assessment.signal is IntradaySignal.FLAT
                or timestamp.time() >= self.config.liquidation_time
                or index == len(bars) - 1
            )
            if should_exit and entry_time is not None:
                exit_price = price * (1 - self.config.slippage_bps / 10_000)
                proceeds = quantity * exit_price - self.config.commission_per_order
                cash += proceeds
                pnl = proceeds - quantity * entry_price - self.config.commission_per_order
                forced += int(
                    timestamp.time() >= self.config.liquidation_time or index == len(bars) - 1
                )
                trades.append(
                    IntradayTrade(entry_time, timestamp, entry_price, exit_price, quantity, pnl)
                )
                quantity = 0.0
                entry_time = None
            can_enter = quantity == 0 and timestamp.time() < self.config.liquidation_time
            if can_enter and assessment.signal is IntradaySignal.LONG:
                entry_price = price * (1 + self.config.slippage_bps / 10_000)
                budget = cash * self.config.position_fraction
                quantity = max(0.0, (budget - self.config.commission_per_order) / entry_price)
                cash -= quantity * entry_price + self.config.commission_per_order
                entry_time = timestamp
        final_equity = cash
        return IntradayBacktestResult(
            initial_capital=self.config.initial_capital,
            final_equity=final_equity,
            total_return=final_equity / self.config.initial_capital - 1,
            trade_count=len(trades),
            forced_liquidations=forced,
            trades=tuple(trades),
        )
