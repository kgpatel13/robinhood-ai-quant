from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.research_assistant import (
    AIResearchAssistant,
    CandidateSource,
    ResearchReport,
    ResearchRequest,
)
from src.research_automation.catalog import ResearchRunCatalog
from src.research_automation.models import (
    AutomationPolicy,
    AutomationRun,
    AutomationStatus,
    PromotionRecommendation,
)


class ResearchAutomationPipeline:
    """Runs an auditable research workflow without submitting broker orders."""

    def __init__(
        self,
        catalog: ResearchRunCatalog,
        assistant: AIResearchAssistant | None = None,
        policy: AutomationPolicy | None = None,
    ) -> None:
        self.catalog = catalog
        self.assistant = assistant or AIResearchAssistant()
        self.policy = policy or AutomationPolicy()

    def execute(
        self,
        request: ResearchRequest,
        candidate_source: CandidateSource,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AutomationRun:
        created_at = datetime.now(UTC)
        run = AutomationRun(
            run_id=str(uuid4()),
            request=request,
            fingerprint=self.fingerprint(request),
            status=AutomationStatus.CREATED,
            created_at=created_at,
            metadata=dict(metadata or {}),
        )
        self.catalog.append(run)
        running = replace(run, status=AutomationStatus.RUNNING)
        self.catalog.append(running)
        try:
            report = self.assistant.run(request, candidate_source)
            completed = replace(
                running,
                status=AutomationStatus.COMPLETED,
                completed_at=datetime.now(UTC),
                report=report,
                promotion_recommendation=self._promotion(report),
            )
            self.catalog.append(completed)
            return completed
        except Exception as exc:
            failed = replace(
                running,
                status=AutomationStatus.FAILED,
                completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {exc}",
            )
            self.catalog.append(failed)
            return failed

    @staticmethod
    def fingerprint(request: ResearchRequest) -> str:
        payload = json.dumps(asdict(request), sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _promotion(self, report: ResearchReport) -> PromotionRecommendation:
        approved = report.approved_candidates
        if len(approved) < self.policy.minimum_recommended_candidates:
            return PromotionRecommendation.NO_ACTION
        recommendation = report.recommendation
        if recommendation is None:
            return PromotionRecommendation.NO_ACTION
        if self.policy.require_manual_review:
            return PromotionRecommendation.MANUAL_REVIEW
        if recommendation.score >= self.policy.paper_score_threshold:
            return PromotionRecommendation.PAPER
        return PromotionRecommendation.SHADOW
