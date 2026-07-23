from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

AllocationMethod = Literal["equal", "fixed", "inverse_volatility"]
RebalanceFrequency = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class PortfolioBacktestConfig:
    initial_cash: float = 100_000.0
    commission_per_order: float = 0.0
    slippage_bps: float = 0.0
    allocation_method: AllocationMethod = "equal"
    fixed_weights: dict[str, float] = field(default_factory=dict)
    volatility_lookback: int = 20
    rebalance_frequency: RebalanceFrequency = "daily"
    max_asset_weight: float = 1.0
    cash_buffer_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.commission_per_order < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")
        if self.volatility_lookback < 2:
            raise ValueError("volatility_lookback must be at least 2")
        if not 0 < self.max_asset_weight <= 1:
            raise ValueError("max_asset_weight must be in (0, 1]")
        if not 0 <= self.cash_buffer_pct < 1:
            raise ValueError("cash_buffer_pct must be in [0, 1)")
        if self.allocation_method == "fixed" and not self.fixed_weights:
            raise ValueError("fixed_weights are required for fixed allocation")


@dataclass(frozen=True)
class PortfolioBacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    holdings: pd.DataFrame
    target_weights: pd.DataFrame
    metrics: dict[str, float | int]
