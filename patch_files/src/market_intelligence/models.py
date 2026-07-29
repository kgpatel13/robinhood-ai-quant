from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MarketState(StrEnum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"
    STRESS = "stress"


class EventSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(StrEnum):
    MACRO = "macro"
    EARNINGS = "earnings"
    CORPORATE_ACTION = "corporate_action"
    MARKET_HOLIDAY = "market_holiday"
    CRYPTO_NETWORK = "crypto_network"


@dataclass(frozen=True)
class MarketEvent:
    event_id: str
    event_type: EventType
    starts_at: datetime
    ends_at: datetime
    severity: EventSeverity
    title: str
    symbols: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if self.ends_at < self.starts_at:
            raise ValueError("ends_at must be on or after starts_at")


@dataclass(frozen=True)
class EventRiskDecision:
    approved: bool
    size_multiplier: float
    reasons: tuple[str, ...]
    matching_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossAssetSnapshot:
    timestamp: datetime
    equity_return: float
    bond_return: float
    dollar_return: float
    volatility_return: float
    credit_return: float = 0.0
    commodity_return: float = 0.0


@dataclass(frozen=True)
class CrossAssetAssessment:
    state: MarketState
    score: float
    confidence: float
    contributions: Mapping[str, float]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SectorObservation:
    sector: str
    return_1m: float
    return_3m: float
    volatility: float
    benchmark_return_1m: float = 0.0


@dataclass(frozen=True)
class SectorScore:
    sector: str
    score: float
    rank: int
    relative_strength: float
    risk_adjusted_momentum: float


@dataclass(frozen=True)
class VolatilityAssessment:
    annualized_volatility: float
    percentile: float
    expansion_ratio: float
    forecast: float
    elevated: bool


@dataclass(frozen=True)
class MarketIntelligenceSnapshot:
    timestamp: datetime
    market_state: MarketState
    confidence: float
    regime: str
    cross_asset_score: float
    volatility: VolatilityAssessment
    sector_ranking: tuple[SectorScore, ...]
    event_risk: EventRiskDecision
    strategy_categories: tuple[str, ...]
    size_multiplier: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
