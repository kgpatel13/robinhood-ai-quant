from __future__ import annotations

from collections.abc import Callable, Iterable

from src.research_assistant.evaluator import EvidenceEvaluator
from src.research_assistant.models import (
    CandidateAssessment,
    CandidateEvidence,
    ResearchReport,
    ResearchRequest,
)
from src.research_assistant.planner import ResearchPlanner

CandidateSource = Callable[[ResearchRequest], Iterable[CandidateEvidence]]


class AIResearchAssistant:
    """Coordinates candidate research without invoking live execution."""

    def __init__(
        self,
        planner: ResearchPlanner | None = None,
        evaluator: EvidenceEvaluator | None = None,
    ) -> None:
        self.planner = planner or ResearchPlanner()
        self.evaluator = evaluator or EvidenceEvaluator()

    def run(self, request: ResearchRequest, candidate_source: CandidateSource) -> ResearchReport:
        plan = self.planner.build(request)
        evidence = tuple(candidate_source(request))[: request.candidate_limit]
        assessments = tuple(
            sorted(
                (self.evaluator.assess(item, request.constraints) for item in evidence),
                key=lambda item: item.score,
                reverse=True,
            )
        )
        recommendation = self._recommendation(assessments)
        summary = self._summary(request, assessments, recommendation)
        return ResearchReport(request, plan, assessments, recommendation, summary)

    @staticmethod
    def _recommendation(
        assessments: tuple[CandidateAssessment, ...],
    ) -> CandidateAssessment | None:
        return next(
            (item for item in assessments if item.decision.value == "recommend"),
            None,
        )

    @staticmethod
    def _summary(
        request: ResearchRequest,
        assessments: tuple[CandidateAssessment, ...],
        recommendation: CandidateAssessment | None,
    ) -> str:
        if not assessments:
            return f"No candidates were produced for: {request.objective}"
        if recommendation is None:
            return (
                f"Evaluated {len(assessments)} candidates; none satisfied every mandatory "
                "research constraint."
            )
        evidence = recommendation.evidence
        return (
            f"Recommended {evidence.candidate_id} ({evidence.strategy}) for manual review "
            f"after evaluating {len(assessments)} candidates."
        )
