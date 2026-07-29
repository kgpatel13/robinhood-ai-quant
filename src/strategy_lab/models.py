from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CandidateStatus(StrEnum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"
    REJECTED = "rejected"


@dataclass(frozen=True)
class StrategyMetrics:
    total_return: float
    sharpe_ratio: float
    maximum_drawdown: float
    turnover: float = 0.0
    trade_count: int = 0
    regime_stability: float = 1.0


@dataclass(frozen=True)
class StrategyCandidate:
    candidate_id: str
    parameters: dict[str, Any]
    metrics: StrategyMetrics
    score: float
    status: CandidateStatus
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaboratoryResult:
    candidates: tuple[StrategyCandidate, ...]

    @property
    def champion(self) -> StrategyCandidate | None:
        return next(
            (item for item in self.candidates if item.status is CandidateStatus.CHAMPION), None
        )
