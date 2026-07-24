from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_per_trade: float = 0.0
    slippage_bps: float = 0.0
    fee_bps: float = 0.0
    max_exposure: float = 1.0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.commission_per_trade < 0 or self.slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError("cost assumptions cannot be negative")
        if not 0.0 < self.max_exposure <= 1.0:
            raise ValueError("max_exposure must be in (0, 1]")


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float | int]
