from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from src.research_assistant import ResearchReport, ResearchRequest


class AutomationStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PromotionRecommendation(StrEnum):
    NO_ACTION = "no_action"
    SHADOW = "shadow"
    PAPER = "paper"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class AutomationPolicy:
    minimum_recommended_candidates: int = 1
    paper_score_threshold: float = 0.75
    require_manual_review: bool = True

    def __post_init__(self) -> None:
        if self.minimum_recommended_candidates < 1:
            raise ValueError("minimum_recommended_candidates must be positive")
        if not 0.0 <= self.paper_score_threshold <= 1.0:
            raise ValueError("paper_score_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class AutomationRun:
    run_id: str
    request: ResearchRequest
    fingerprint: str
    status: AutomationStatus
    created_at: datetime
    completed_at: datetime | None = None
    report: ResearchReport | None = None
    promotion_recommendation: PromotionRecommendation = PromotionRecommendation.NO_ACTION
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.fingerprint.strip():
            raise ValueError("run_id and fingerprint must not be empty")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["promotion_recommendation"] = self.promotion_recommendation.value
        payload["created_at"] = self.created_at.astimezone(UTC).isoformat()
        payload["completed_at"] = (
            self.completed_at.astimezone(UTC).isoformat() if self.completed_at else None
        )
        return payload
