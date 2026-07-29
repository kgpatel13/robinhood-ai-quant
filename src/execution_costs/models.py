from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AssetClass(StrEnum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    FOREX = "forex"


class TradingHorizon(StrEnum):
    SCALPING = "scalping"
    DAY = "day"
    SWING = "swing"
    WEEKLY = "weekly"


@dataclass(frozen=True)
class ExecutionCostProfile:
    spread_bps: float
    base_slippage_bps: float
    impact_coefficient: float
    latency_bps: float = 0.0
    commission_per_order: float = 0.0
    commission_per_unit: float = 0.0
    borrow_bps_annual: float = 0.0
    financing_bps_annual: float = 0.0
    maximum_participation_rate: float = 0.1

    def __post_init__(self) -> None:
        values = (
            self.spread_bps,
            self.base_slippage_bps,
            self.impact_coefficient,
            self.latency_bps,
            self.commission_per_order,
            self.commission_per_unit,
            self.borrow_bps_annual,
            self.financing_bps_annual,
        )
        if any(value < 0 for value in values):
            raise ValueError("cost inputs must be non-negative")
        if not 0 < self.maximum_participation_rate <= 1:
            raise ValueError("maximum_participation_rate must be in (0, 1]")


@dataclass(frozen=True)
class ExecutionCostRequest:
    price: float
    quantity: float
    average_daily_volume: float
    holding_days: float = 0.0
    is_short: bool = False
    volatility: float = 0.0

    def __post_init__(self) -> None:
        if self.price <= 0 or self.quantity <= 0 or self.average_daily_volume <= 0:
            raise ValueError("price, quantity, and average_daily_volume must be positive")
        if self.holding_days < 0 or self.volatility < 0:
            raise ValueError("holding_days and volatility must be non-negative")


@dataclass(frozen=True)
class ExecutionCostEstimate:
    notional: float
    spread_cost: float
    slippage_cost: float
    market_impact_cost: float
    latency_cost: float
    commission_cost: float
    borrow_cost: float
    financing_cost: float
    total_cost: float
    total_bps: float
    fill_ratio: float
