from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TradeIntentDecision(StrEnum):
    APPROVE = "approve"
    REDUCE = "reduce"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class TradeIntentRequest:
    trade_id: str
    symbol: str
    strategy: str
    timestamp: datetime
    alpha_score: float
    alpha_confidence: float
    regime_approved: bool
    regime_size_multiplier: float
    market_quality_decision: str
    market_quality_multiplier: float
    portfolio_health_action: str
    requested_notional: float
    minimum_alpha_score: float = 0.10
    minimum_alpha_confidence: float = 0.40

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not self.trade_id.strip():
            raise ValueError("trade_id must not be empty")
        if not self.symbol.strip() or not self.strategy.strip():
            raise ValueError("symbol and strategy must not be empty")
        if not -1.0 <= self.alpha_score <= 1.0:
            raise ValueError("alpha_score must be in [-1, 1]")
        if not 0.0 <= self.alpha_confidence <= 1.0:
            raise ValueError("alpha_confidence must be in [0, 1]")
        if not 0.0 <= self.regime_size_multiplier <= 1.0:
            raise ValueError("regime_size_multiplier must be in [0, 1]")
        if not 0.0 <= self.market_quality_multiplier <= 1.0:
            raise ValueError("market_quality_multiplier must be in [0, 1]")
        if self.requested_notional <= 0:
            raise ValueError("requested_notional must be positive")


@dataclass(frozen=True, slots=True)
class TradeIntentResult:
    trade_id: str
    symbol: str
    strategy: str
    decision: TradeIntentDecision
    approved_notional: float
    side: str
    confidence: float
    size_multiplier: float
    reasons: tuple[str, ...]
