from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketRegime(StrEnum):
    STRONG_BULL = "strong_bull"
    WEAK_BULL = "weak_bull"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    PANIC = "panic"
    RECOVERY = "recovery"
    LOW_LIQUIDITY = "low_liquidity"


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: MarketRegime
    confidence: float
    trend_return: float
    annualized_volatility: float
    relative_volume: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class StrategyRegimePolicy:
    allowed_regimes: frozenset[MarketRegime]
    minimum_confidence: float = 0.55


@dataclass(frozen=True)
class RegimeGateDecision:
    approved: bool
    size_multiplier: float
    reason: str
