from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromotionDecision(StrEnum):
    PROMOTE_TO_SHADOW = "promote_to_shadow"
    PROMOTE_TO_PAPER = "promote_to_paper"
    HOLD = "hold"
    DEMOTE = "demote"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    strategy: str
    current_stage: str
    health_score: float
    paper_trades: int
    out_of_sample_sharpe: float
    maximum_drawdown: float
    execution_slippage_bps: float
    regime_coverage: int
    consecutive_healthy_reviews: int
    hard_risk_breach: bool = False

    def __post_init__(self) -> None:
        if not self.strategy.strip():
            raise ValueError("strategy must not be empty")
        if not 0.0 <= self.health_score <= 100.0:
            raise ValueError("health_score must be in [0, 100]")
        if self.paper_trades < 0 or self.regime_coverage < 0:
            raise ValueError("counts cannot be negative")
        if self.maximum_drawdown < 0:
            raise ValueError("maximum_drawdown must be non-negative")
        if self.execution_slippage_bps < 0:
            raise ValueError("execution_slippage_bps must be non-negative")


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    minimum_health_score: float = 80.0
    minimum_paper_trades: int = 30
    minimum_out_of_sample_sharpe: float = 1.0
    maximum_drawdown: float = 0.15
    maximum_slippage_bps: float = 35.0
    minimum_regime_coverage: int = 2
    minimum_consecutive_reviews: int = 3


@dataclass(frozen=True, slots=True)
class PromotionReview:
    strategy: str
    decision: PromotionDecision
    target_stage: str
    eligible: bool
    reasons: tuple[str, ...]
