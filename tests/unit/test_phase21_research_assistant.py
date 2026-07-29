from __future__ import annotations

import json

import pytest

from src.research_assistant import (
    AIResearchAssistant,
    CandidateEvidence,
    EvidenceEvaluator,
    ResearchConstraints,
    ResearchDecision,
    ResearchPlanner,
    ResearchRequest,
    write_research_report,
)


def evidence(
    candidate_id: str = "candidate-1",
    *,
    sharpe: float = 1.6,
    drawdown: float = 0.10,
    trades: int = 80,
    regimes: int = 3,
    stability: float = 0.80,
    slippage: float = 8.0,
    out_of_sample: bool = True,
) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=candidate_id,
        strategy="momentum",
        parameters={"lookback": 20},
        total_return=0.25,
        sharpe_ratio=sharpe,
        maximum_drawdown=drawdown,
        trade_count=trades,
        regime_coverage=regimes,
        stability=stability,
        slippage_bps=slippage,
        out_of_sample=out_of_sample,
    )


def request(limit: int = 25) -> ResearchRequest:
    return ResearchRequest(
        objective="Find a robust swing strategy",
        universe=("AAPL", "MSFT"),
        horizons=("swing",),
        candidate_limit=limit,
    )


def test_request_requires_universe() -> None:
    with pytest.raises(ValueError, match="universe"):
        ResearchRequest("objective", (), ("swing",))


def test_planner_requires_out_of_sample_and_manual_approval() -> None:
    plan = ResearchPlanner().build(request())
    assert "out_of_sample_evidence_required" in plan.safety_requirements
    assert "manual_approval_required" in plan.safety_requirements


def test_evaluator_recommends_candidate_that_passes_all_gates() -> None:
    assessment = EvidenceEvaluator().assess(evidence(), ResearchConstraints())
    assert assessment.decision is ResearchDecision.RECOMMEND
    assert assessment.reasons == ()


def test_evaluator_rejects_excessive_drawdown() -> None:
    assessment = EvidenceEvaluator().assess(
        evidence(drawdown=0.25),
        ResearchConstraints(maximum_drawdown=0.15),
    )
    assert assessment.decision is ResearchDecision.REJECT
    assert "drawdown_above_maximum" in assessment.reasons


def test_evaluator_reviews_soft_gate_failure() -> None:
    assessment = EvidenceEvaluator().assess(evidence(trades=10), ResearchConstraints())
    assert assessment.decision is ResearchDecision.REVIEW
    assert "insufficient_trades" in assessment.reasons


def test_missing_out_of_sample_evidence_is_rejected() -> None:
    assessment = EvidenceEvaluator().assess(
        evidence(out_of_sample=False),
        ResearchConstraints(),
    )
    assert assessment.decision is ResearchDecision.REJECT


def test_assistant_ranks_and_recommends_best_eligible_candidate() -> None:
    assistant = AIResearchAssistant()
    candidates = [evidence("weak", sharpe=0.8), evidence("strong", sharpe=2.0)]
    report = assistant.run(request(), lambda _: candidates)
    assert report.assessments[0].evidence.candidate_id == "strong"
    assert report.recommendation is not None
    assert report.recommendation.evidence.candidate_id == "strong"


def test_assistant_enforces_candidate_limit() -> None:
    candidates = [evidence(f"candidate-{index}") for index in range(5)]
    report = AIResearchAssistant().run(request(limit=2), lambda _: candidates)
    assert len(report.assessments) == 2


def test_assistant_handles_empty_candidate_source() -> None:
    report = AIResearchAssistant().run(request(), lambda _: ())
    assert report.recommendation is None
    assert "No candidates" in report.summary


def test_report_writer_creates_json_and_markdown(tmp_path) -> None:
    report = AIResearchAssistant().run(request(), lambda _: [evidence()])
    paths = write_research_report(report, tmp_path)
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["evidence"]["candidate_id"] == "candidate-1"
    assert "Manual approval" in paths["markdown"].read_text(encoding="utf-8")
