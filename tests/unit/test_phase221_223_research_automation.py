from pathlib import Path

from src.research_assistant import CandidateEvidence, ResearchRequest
from src.research_automation import (
    AutomationPolicy,
    AutomationStatus,
    PromotionRecommendation,
    ResearchAutomationPipeline,
    ResearchRunCatalog,
)


def request() -> ResearchRequest:
    return ResearchRequest("Find durable swing alpha", ("SPY", "QQQ"), ("swing",))


def good_candidate(_: ResearchRequest) -> tuple[CandidateEvidence, ...]:
    return (
        CandidateEvidence(
            "candidate-1",
            "momentum",
            {"lookback": 20},
            0.25,
            1.8,
            0.10,
            120,
            4,
            0.82,
            8.0,
        ),
    )


def test_fingerprint_is_deterministic(tmp_path: Path) -> None:
    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    assert pipeline.fingerprint(request()) == pipeline.fingerprint(request())


def test_fingerprint_changes_with_request(tmp_path: Path) -> None:
    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    changed = ResearchRequest("Different objective", ("SPY",), ("day",))
    assert pipeline.fingerprint(request()) != pipeline.fingerprint(changed)


def test_pipeline_completes_and_catalogs_lifecycle(tmp_path: Path) -> None:
    catalog = ResearchRunCatalog(tmp_path / "runs.jsonl")
    run = ResearchAutomationPipeline(catalog).execute(request(), good_candidate)
    assert run.status is AutomationStatus.COMPLETED
    assert len(catalog.entries()) == 3


def test_pipeline_requires_manual_review_by_default(tmp_path: Path) -> None:
    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    run = pipeline.execute(request(), good_candidate)
    assert run.promotion_recommendation is PromotionRecommendation.MANUAL_REVIEW


def test_pipeline_can_recommend_paper_without_manual_gate(tmp_path: Path) -> None:
    policy = AutomationPolicy(require_manual_review=False, paper_score_threshold=0.50)
    pipeline = ResearchAutomationPipeline(
        ResearchRunCatalog(tmp_path / "runs.jsonl"), policy=policy
    )
    run = pipeline.execute(request(), good_candidate)
    assert run.promotion_recommendation is PromotionRecommendation.PAPER


def test_pipeline_recommends_no_action_without_candidates(tmp_path: Path) -> None:
    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    run = pipeline.execute(request(), lambda _: ())
    assert run.promotion_recommendation is PromotionRecommendation.NO_ACTION


def test_pipeline_contains_candidate_source_failure(tmp_path: Path) -> None:
    def broken(_: ResearchRequest) -> tuple[CandidateEvidence, ...]:
        raise RuntimeError("source unavailable")

    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    run = pipeline.execute(request(), broken)
    assert run.status is AutomationStatus.FAILED
    assert run.error == "RuntimeError: source unavailable"


def test_catalog_latest_returns_last_state(tmp_path: Path) -> None:
    catalog = ResearchRunCatalog(tmp_path / "runs.jsonl")
    run = ResearchAutomationPipeline(catalog).execute(request(), good_candidate)
    latest = catalog.latest(run.run_id)
    assert latest is not None
    assert latest["status"] == "completed"


def test_metadata_is_preserved(tmp_path: Path) -> None:
    pipeline = ResearchAutomationPipeline(ResearchRunCatalog(tmp_path / "runs.jsonl"))
    run = pipeline.execute(request(), good_candidate, metadata={"dataset": "v3"})
    assert run.metadata == {"dataset": "v3"}


def test_policy_validates_thresholds() -> None:
    try:
        AutomationPolicy(paper_score_threshold=1.1)
    except ValueError as exc:
        assert "paper_score_threshold" in str(exc)
    else:
        raise AssertionError("expected ValueError")
