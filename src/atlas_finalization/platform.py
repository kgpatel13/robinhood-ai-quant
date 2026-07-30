from __future__ import annotations

from dataclasses import dataclass

from src.atlas_finalization.models import (
    HealthSnapshot,
    OperationalAssessment,
    PaperSessionMetrics,
    ValidationMetrics,
    ValidationScorecard,
)
from src.atlas_finalization.operations import OperationalHealthAssessor, PaperReadinessEvaluator
from src.atlas_finalization.research import StrategyValidationEngine


@dataclass(frozen=True, slots=True)
class FinalReadinessReport:
    strategy: ValidationScorecard
    operations: OperationalAssessment
    paper_ready: bool
    paper_reasons: tuple[str, ...]
    canary_recommended: bool


class AtlasFinalizationPlatform:
    def __init__(
        self,
        validation: StrategyValidationEngine | None = None,
        operations: OperationalHealthAssessor | None = None,
        paper: PaperReadinessEvaluator | None = None,
    ) -> None:
        self.validation = validation or StrategyValidationEngine()
        self.operations = operations or OperationalHealthAssessor()
        self.paper = paper or PaperReadinessEvaluator()

    def assess(
        self,
        strategy_id: str,
        validation_metrics: ValidationMetrics,
        health: HealthSnapshot,
        paper_metrics: PaperSessionMetrics,
    ) -> FinalReadinessReport:
        strategy = self.validation.score(strategy_id, validation_metrics)
        operations = self.operations.assess(health)
        paper_ready, paper_reasons = self.paper.evaluate(paper_metrics)
        canary_recommended = (
            strategy.decision.value == "promote"
            and operations.status.value == "healthy"
            and paper_ready
        )
        return FinalReadinessReport(
            strategy=strategy,
            operations=operations,
            paper_ready=paper_ready,
            paper_reasons=paper_reasons,
            canary_recommended=canary_recommended,
        )
