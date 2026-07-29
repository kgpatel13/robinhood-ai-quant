from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SizingMethod(StrEnum):
    FIXED_FRACTIONAL = "fixed_fractional"
    FRACTIONAL_KELLY = "fractional_kelly"
    VOLATILITY_TARGET = "volatility_target"


@dataclass(frozen=True)
class CapitalAllocationRequest:
    strategy: str
    portfolio_equity: float
    confidence: float
    expected_win_probability: float
    payoff_ratio: float
    realized_volatility: float
    current_drawdown: float = 0.0


@dataclass(frozen=True)
class AllocationPolicy:
    method: SizingMethod = SizingMethod.FRACTIONAL_KELLY
    fixed_fraction: float = 0.01
    kelly_fraction: float = 0.25
    target_volatility: float = 0.15
    maximum_allocation: float = 0.10
    maximum_drawdown: float = 0.20
    daily_risk_budget: float = 0.02


@dataclass(frozen=True)
class CapitalAllocationResult:
    strategy: str
    allocation_fraction: float
    allocated_capital: float
    risk_budget: float
    sizing_method: SizingMethod
    reasons: tuple[str, ...]
