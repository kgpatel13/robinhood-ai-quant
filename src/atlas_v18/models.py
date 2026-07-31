from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MarketRegime(StrEnum):
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    INSUFFICIENT_DATA = "insufficient_data"


class SignalAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    regime: MarketRegime
    confidence: float
    trend_return: float
    annualized_volatility: float
    moving_average_gap: float


@dataclass(frozen=True, slots=True)
class StrategySignal:
    strategy: str
    action: SignalAction
    confidence: float
    expected_return: float = 0.0
    rationale: str = ""
    regime_affinity: frozenset[MarketRegime] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class EnsembleDecision:
    action: SignalAction
    confidence: float
    weighted_buy: float
    weighted_sell: float
    weighted_wait: float
    contributors: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class PositionSizingInput:
    equity: float
    price: float
    confidence: float
    annualized_volatility: float
    current_drawdown: float = 0.0
    current_exposure_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class PositionSize:
    quantity: float
    notional: float
    portfolio_pct: float
    risk_budget_pct: float
    capped_by: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    observations: int
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    expectancy: float


@dataclass(frozen=True, slots=True)
class AtlasDecision:
    regime: RegimeSnapshot
    ensemble: EnsembleDecision
    size: PositionSize
    safety: SafetyDecision
