from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OptimizationObjective(StrEnum):
    MINIMUM_VARIANCE = "minimum_variance"
    RISK_PARITY = "risk_parity"
    MAXIMUM_DIVERSIFICATION = "maximum_diversification"


@dataclass(frozen=True)
class PortfolioConstraints:
    minimum_weight: float = 0.0
    maximum_weight: float = 1.0
    cash_weight: float = 0.0

    def validate(self, asset_count: int) -> None:
        if asset_count < 1:
            raise ValueError("asset_count must be positive")
        if not 0.0 <= self.minimum_weight <= self.maximum_weight <= 1.0:
            raise ValueError("weights must satisfy 0 <= minimum <= maximum <= 1")
        if not 0.0 <= self.cash_weight < 1.0:
            raise ValueError("cash_weight must be in [0, 1)")
        investable = 1.0 - self.cash_weight
        if self.minimum_weight * asset_count > investable + 1e-12:
            raise ValueError("minimum weights exceed investable capital")
        if self.maximum_weight * asset_count < investable - 1e-12:
            raise ValueError("maximum weights cannot fully invest the portfolio")


@dataclass(frozen=True)
class PortfolioOptimizationResult:
    objective: OptimizationObjective
    weights: dict[str, float]
    cash_weight: float
    expected_volatility: float
    diversification_ratio: float
    converged: bool
    message: str
