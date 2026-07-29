import pytest

from src.self_improving_ai import (
    AdaptiveParameterTuner,
    FeatureCandidate,
    FeatureEvolutionEngine,
    LearningPolicy,
    PolicyFeedback,
    SafeguardedPolicyUpdater,
    StrategyLifecycle,
    StrategyLifecycleManager,
    StrategyPerformance,
)


def test_strategy_is_retired_for_bad_sharpe() -> None:
    manager = StrategyLifecycleManager()
    update = manager.update(StrategyPerformance("s1", 100, -0.5, 0.1, 0.4, -0.02), 0.3)
    assert update.lifecycle is StrategyLifecycle.RETIRED
    assert update.new_weight == 0.0


def test_strategy_is_retired_for_excess_drawdown() -> None:
    manager = StrategyLifecycleManager()
    update = manager.update(StrategyPerformance("s1", 100, 1.2, 0.4, 0.6, 0.03), 0.3)
    assert update.lifecycle is StrategyLifecycle.RETIRED


def test_strategy_is_watched_when_evidence_is_insufficient() -> None:
    policy = LearningPolicy(minimum_observations=50, watch_sharpe=0.0)
    update = StrategyLifecycleManager(policy).update(
        StrategyPerformance("s1", 10, 0.5, 0.1, 0.6, 0.02), 0.3
    )
    assert update.lifecycle is StrategyLifecycle.WATCH


def test_good_strategy_weight_increases_with_bounds() -> None:
    update = StrategyLifecycleManager().update(
        StrategyPerformance("s1", 100, 2.0, 0.1, 0.7, 0.1), 0.7
    )
    assert update.lifecycle is StrategyLifecycle.ACTIVE
    assert update.new_weight <= 0.75
    assert update.new_weight > 0.7


def test_feature_evolution_selects_stable_predictive_feature() -> None:
    result = FeatureEvolutionEngine().select(
        [
            FeatureCandidate("good", 0.2, 0.8, 0.2),
            FeatureCandidate("weak", 0.01, 0.9, 0.2),
        ]
    )
    assert result.selected == ("good",)
    assert "weak" in result.rejected


def test_feature_evolution_rejects_redundant_feature() -> None:
    result = FeatureEvolutionEngine().select([FeatureCandidate("copy", 0.3, 0.9, 0.95)])
    assert "copy" in result.rejected


def test_policy_update_is_normalized_and_risk_adjusted() -> None:
    updater = SafeguardedPolicyUpdater(learning_rate=0.1, maximum_step=0.05)
    result = updater.update(
        {"buy": 0.5, "hold": 0.5},
        [PolicyFeedback("buy", reward=1.0, risk_penalty=0.8)],
    )
    assert sum(result.values()) == pytest.approx(1.0)
    assert result["buy"] > 0.5


def test_policy_update_ignores_unknown_action() -> None:
    result = SafeguardedPolicyUpdater().update(
        {"buy": 1.0}, [PolicyFeedback("sell", reward=10.0, risk_penalty=0.0)]
    )
    assert result == {"buy": 1.0}


def test_parameter_tuner_selects_best_candidate() -> None:
    result = AdaptiveParameterTuner().tune(
        [{"window": 10}, {"window": 20}],
        lambda parameters: float(parameters["window"]),
    )
    assert result.parameters == {"window": 20}
    assert result.score == 20.0


def test_parameter_tuner_rejects_empty_candidate_set() -> None:
    with pytest.raises(ValueError):
        AdaptiveParameterTuner().tune([], lambda _: 0.0)
