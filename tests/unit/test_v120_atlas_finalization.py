from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.atlas_finalization import (
    AtlasFinalizationPlatform,
    ChangeProposal,
    ExperimentRecord,
    ExperimentRegistry,
    HealthSnapshot,
    LearningGovernanceGate,
    MonteCarloTradeSimulator,
    OperationalHealthAssessor,
    OperationStatus,
    PaperReadinessEvaluator,
    PaperSessionMetrics,
    PerformanceAttributionEngine,
    StrategyValidationEngine,
    TradeAttributionInput,
    ValidationDecision,
    ValidationMetrics,
)


def good_validation() -> ValidationMetrics:
    return ValidationMetrics(
        annualized_return=0.18,
        sharpe_ratio=1.35,
        maximum_drawdown=0.11,
        trade_count=180,
        out_of_sample_return=0.12,
        cost_adjusted_return=0.10,
        parameter_stability=0.82,
        regime_coverage=0.75,
    )


def good_health() -> HealthSnapshot:
    return HealthSnapshot(
        generated_at=datetime.now(UTC),
        market_data_fresh=True,
        broker_connected=True,
        reconciliation_clean=True,
        kill_switch_active=False,
        error_rate=0.01,
        decision_latency_ms=120.0,
        broker_latency_ms=240.0,
    )


def good_paper() -> PaperSessionMetrics:
    return PaperSessionMetrics(
        trading_days=90,
        submitted_orders=400,
        filled_orders=390,
        rejected_orders=10,
        realized_pnl=2_500.0,
        maximum_drawdown=0.08,
    )


def test_validation_promotes_strong_strategy() -> None:
    result = StrategyValidationEngine().score("momentum-v1", good_validation())
    assert result.decision is ValidationDecision.PROMOTE
    assert result.score == 100.0


def test_validation_rejects_weak_strategy() -> None:
    metrics = ValidationMetrics(0.0, 0.1, 0.35, 10, -0.1, -0.2, 0.2, 0.2)
    result = StrategyValidationEngine().score("weak", metrics)
    assert result.decision is ValidationDecision.REJECT
    assert result.reasons


def test_validation_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="trade_count"):
        ValidationMetrics(0, 0, 0, -1, 0, 0, 0, 0)


def test_monte_carlo_is_deterministic() -> None:
    first = MonteCarloTradeSimulator.simulate([0.02, -0.01, 0.015], simulations=100, seed=9)
    second = MonteCarloTradeSimulator.simulate([0.02, -0.01, 0.015], simulations=100, seed=9)
    assert first == second


def test_monte_carlo_rejects_empty_returns() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        MonteCarloTradeSimulator.simulate([])


def test_health_assessment_is_healthy() -> None:
    result = OperationalHealthAssessor().assess(good_health())
    assert result.status is OperationStatus.HEALTHY
    assert result.score >= 80


def test_health_assessment_halts_on_stale_data() -> None:
    snapshot = HealthSnapshot(
        generated_at=datetime.now(UTC),
        market_data_fresh=False,
        broker_connected=True,
        reconciliation_clean=True,
        kill_switch_active=False,
        error_rate=0,
        decision_latency_ms=0,
        broker_latency_ms=0,
    )
    result = OperationalHealthAssessor().assess(snapshot)
    assert result.status is OperationStatus.HALTED
    assert "market data stale" in result.reasons


def test_health_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        HealthSnapshot(datetime.now(), True, True, True, False, 0, 0, 0)


def test_paper_readiness_passes_clean_history() -> None:
    ready, reasons = PaperReadinessEvaluator().evaluate(good_paper())
    assert ready
    assert reasons == ()


def test_paper_readiness_blocks_duplicates() -> None:
    metrics = PaperSessionMetrics(90, 400, 390, 10, 100, 0.08, duplicate_orders=1)
    ready, reasons = PaperReadinessEvaluator().evaluate(metrics)
    assert not ready
    assert "duplicate orders detected" in reasons


def test_paper_session_validates_order_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        PaperSessionMetrics(1, 1, 1, 1, 0, 0)


def test_attribution_reconciles_to_net_pnl() -> None:
    item = TradeAttributionInput("trade-1", 100.0, 2.0, 3.0, 0.5, 0.3, 0.2)
    result = PerformanceAttributionEngine.attribute(item)
    contributions = (
        result.strategy_contribution + result.agent_contribution + result.sizing_contribution
    )
    assert result.net_pnl == 95.0
    assert contributions == pytest.approx(result.net_pnl)
    assert result.cost_drag == 5.0


def test_attribution_defaults_to_strategy_when_weights_zero() -> None:
    item = TradeAttributionInput("trade-2", 20.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    result = PerformanceAttributionEngine.attribute(item)
    assert result.strategy_contribution == 20.0


def test_experiment_registry_adds_and_lists() -> None:
    registry = ExperimentRegistry()
    record = experiment_record("exp-1")
    registry.add(record)
    assert registry.get("exp-1") == record
    assert registry.list() == (record,)


def test_experiment_registry_rejects_duplicate() -> None:
    registry = ExperimentRegistry()
    record = experiment_record("exp-1")
    registry.add(record)
    with pytest.raises(ValueError, match="duplicate"):
        registry.add(record)


def test_experiment_fingerprint_is_stable() -> None:
    record = experiment_record("exp-1")
    assert ExperimentRegistry.fingerprint(record) == ExperimentRegistry.fingerprint(record)


def test_experiment_registry_writes_json(tmp_path: Path) -> None:
    registry = ExperimentRegistry()
    registry.add(experiment_record("exp-1"))
    output = registry.write_json(tmp_path / "experiments.json")
    assert output.exists()
    assert "exp-1" in output.read_text(encoding="utf-8")


def test_governance_requires_human_approval() -> None:
    scorecard = StrategyValidationEngine().score("strategy", good_validation())
    proposal = ChangeProposal("p1", "strategy", "1", "2", scorecard, "1")
    decision = LearningGovernanceGate.decide(proposal, human_approved=False)
    assert not decision.approved
    assert decision.active_version == "1"


def test_governance_approves_promoted_candidate() -> None:
    scorecard = StrategyValidationEngine().score("strategy", good_validation())
    proposal = ChangeProposal("p1", "strategy", "1", "2", scorecard, "1")
    decision = LearningGovernanceGate.decide(proposal, human_approved=True)
    assert decision.approved
    assert decision.active_version == "2"


def test_governance_rollback_uses_recorded_version() -> None:
    scorecard = StrategyValidationEngine().score("strategy", good_validation())
    proposal = ChangeProposal("p1", "strategy", "1", "2", scorecard, "0.9")
    assert LearningGovernanceGate.rollback(proposal).active_version == "0.9"


def test_integrated_platform_recommends_canary() -> None:
    report = AtlasFinalizationPlatform().assess(
        "strategy", good_validation(), good_health(), good_paper()
    )
    assert report.canary_recommended


def test_integrated_platform_blocks_bad_operations() -> None:
    health = HealthSnapshot(datetime.now(UTC), True, False, True, False, 0, 0, 0)
    report = AtlasFinalizationPlatform().assess("strategy", good_validation(), health, good_paper())
    assert not report.canary_recommended
    assert report.operations.status is OperationStatus.HALTED


def test_integrated_platform_blocks_weak_strategy() -> None:
    weak = ValidationMetrics(0, 0.1, 0.30, 5, -0.1, -0.1, 0.1, 0.1)
    report = AtlasFinalizationPlatform().assess("weak", weak, good_health(), good_paper())
    assert not report.canary_recommended


def experiment_record(experiment_id: str) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        strategy_id="momentum",
        strategy_version="1.0",
        code_version="12.0.0",
        dataset_id="SPY-2015-2025",
        parameters={"lookback": 20, "threshold": 0.1},
        metrics=good_validation(),
        created_at=datetime.now(UTC),
    )
