from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResearchDecision(StrEnum):
    RECOMMEND = "recommend"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ResearchConstraints:
    minimum_sharpe: float = 1.0
    maximum_drawdown: float = 0.15
    minimum_trades: int = 30
    minimum_regime_coverage: int = 2
    maximum_slippage_bps: float = 35.0
    minimum_stability: float = 0.60

    def __post_init__(self) -> None:
        if self.maximum_drawdown <= 0:
            raise ValueError("maximum_drawdown must be positive")
        if self.minimum_trades < 0 or self.minimum_regime_coverage < 0:
            raise ValueError("minimum counts cannot be negative")
        if self.maximum_slippage_bps < 0:
            raise ValueError("maximum_slippage_bps cannot be negative")
        if not 0.0 <= self.minimum_stability <= 1.0:
            raise ValueError("minimum_stability must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    objective: str
    universe: tuple[str, ...]
    horizons: tuple[str, ...]
    candidate_limit: int = 25
    constraints: ResearchConstraints = field(default_factory=ResearchConstraints)
    assumptions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        if not self.universe:
            raise ValueError("universe must not be empty")
        if not self.horizons:
            raise ValueError("horizons must not be empty")
        if self.candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    candidate_id: str
    strategy: str
    parameters: dict[str, Any]
    total_return: float
    sharpe_ratio: float
    maximum_drawdown: float
    trade_count: int
    regime_coverage: int
    stability: float
    slippage_bps: float
    out_of_sample: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.strategy.strip():
            raise ValueError("candidate_id and strategy must not be empty")
        if self.maximum_drawdown < 0 or self.slippage_bps < 0:
            raise ValueError("drawdown and slippage must be non-negative")
        if self.trade_count < 0 or self.regime_coverage < 0:
            raise ValueError("counts cannot be negative")
        if not 0.0 <= self.stability <= 1.0:
            raise ValueError("stability must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    evidence: CandidateEvidence
    score: float
    decision: ResearchDecision
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    objective: str
    steps: tuple[str, ...]
    required_evidence: tuple[str, ...]
    safety_requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchReport:
    request: ResearchRequest
    plan: ResearchPlan
    assessments: tuple[CandidateAssessment, ...]
    recommendation: CandidateAssessment | None
    summary: str

    @property
    def approved_candidates(self) -> tuple[CandidateAssessment, ...]:
        return tuple(
            item for item in self.assessments if item.decision is ResearchDecision.RECOMMEND
        )
