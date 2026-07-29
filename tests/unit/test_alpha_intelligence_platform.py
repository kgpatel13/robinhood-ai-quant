from __future__ import annotations

from src.alpha_intelligence import (
    AlphaCandidate,
    AlphaIntelligencePlatform,
    ExperimentCatalog,
    ParameterSearch,
    ParameterSpec,
    PromotionPipeline,
    PromotionStage,
    RobustnessEvaluator,
    RobustnessMetrics,
    SearchMethod,
    StrategyDefinition,
    StrategyFamily,
    StrategyRegistry,
    default_strategy_templates,
)


def _candidate(
    strategy_id: str, parameters: dict[str, object], good: bool = True
) -> AlphaCandidate:
    return AlphaCandidate(
        candidate_id=f"{strategy_id}-{parameters}",
        strategy_id=strategy_id,
        parameters=parameters,
        total_return=0.20 if good else -0.05,
        sharpe_ratio=1.25 if good else 0.20,
        maximum_drawdown=-0.12 if good else -0.40,
        trade_count=60 if good else 3,
        robustness=RobustnessMetrics(
            out_of_sample_return=0.10 if good else -0.02,
            walk_forward_sharpe=1.05 if good else 0.10,
            monte_carlo_survival_rate=0.85 if good else 0.30,
            parameter_stability=0.80 if good else 0.20,
            regime_coverage=0.75 if good else 0.20,
            cost_adjusted_return=0.08 if good else -0.03,
        ),
    )


def test_default_templates_cover_multiple_families() -> None:
    templates = default_strategy_templates()
    assert len(templates) >= 4
    assert len({template.family for template in templates}) >= 4


def test_parameter_spec_rejects_empty_values() -> None:
    try:
        ParameterSpec("window", ())
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_strategy_definition_rejects_duplicate_parameter_names() -> None:
    parameter = ParameterSpec("window", (10, 20))
    try:
        StrategyDefinition("x", "X", StrategyFamily.TREND, "1", (parameter, parameter))
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_registry_returns_latest_version() -> None:
    registry = StrategyRegistry()
    registry.register(StrategyDefinition("x", "X", StrategyFamily.TREND, "1.0.0"))
    registry.register(StrategyDefinition("x", "X", StrategyFamily.TREND, "2.0.0"))
    assert registry.get("x").version == "2.0.0"


def test_registry_rejects_duplicate_version() -> None:
    definition = StrategyDefinition("x", "X", StrategyFamily.TREND, "1.0.0")
    registry = StrategyRegistry((definition,))
    try:
        registry.register(definition)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_grid_search_is_deterministic() -> None:
    result = ParameterSearch().generate({"slow": (20, 30), "fast": (5, 10)})
    assert result[0] == {"fast": 5, "slow": 20}
    assert len(result) == 4


def test_random_search_respects_limit_and_seed() -> None:
    search = ParameterSearch()
    first = search.generate(
        {"x": tuple(range(10))}, SearchMethod.RANDOM, maximum_candidates=3, seed=7
    )
    second = search.generate(
        {"x": tuple(range(10))}, SearchMethod.RANDOM, maximum_candidates=3, seed=7
    )
    assert first == second
    assert len(first) == 3


def test_robustness_accepts_good_candidate() -> None:
    candidate = RobustnessEvaluator().evaluate(_candidate("x", {"a": 1}))
    assert candidate.rejection_reasons == ()
    assert candidate.score > 0


def test_robustness_rejects_weak_candidate() -> None:
    candidate = RobustnessEvaluator().evaluate(_candidate("x", {"a": 1}, good=False))
    assert "sharpe_below_minimum" in candidate.rejection_reasons
    assert "drawdown_above_maximum" in candidate.rejection_reasons
    assert "insufficient_trades" in candidate.rejection_reasons


def test_experiment_fingerprint_is_stable() -> None:
    first = ExperimentCatalog.fingerprint("x", "d", {"b": 2, "a": 1})
    second = ExperimentCatalog.fingerprint("x", "d", {"a": 1, "b": 2})
    assert first == second


def test_experiment_catalog_rejects_duplicate_id() -> None:
    catalog = ExperimentCatalog()
    candidate = _candidate("x", {"a": 1})
    catalog.add("e1", "dataset", candidate)
    try:
        catalog.add("e1", "dataset", candidate)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_promotion_advances_good_candidate_one_stage() -> None:
    candidate = RobustnessEvaluator().evaluate(_candidate("x", {"a": 1}))
    decision = PromotionPipeline().recommend(candidate, PromotionStage.RESEARCH)
    assert decision.approved
    assert decision.recommended_stage is PromotionStage.SIMULATION


def test_promotion_blocks_rejected_candidate() -> None:
    candidate = RobustnessEvaluator().evaluate(_candidate("x", {"a": 1}, good=False))
    decision = PromotionPipeline().recommend(candidate, PromotionStage.RESEARCH)
    assert not decision.approved
    assert decision.recommended_stage is PromotionStage.RESEARCH


def test_small_capital_requires_manual_approval() -> None:
    candidate = RobustnessEvaluator().evaluate(_candidate("x", {"a": 1}))
    decision = PromotionPipeline().recommend(candidate, PromotionStage.SMALL_CAPITAL)
    assert not decision.approved
    assert "manual_approval_required" in decision.reasons


def test_platform_discovers_and_ranks_champion() -> None:
    platform = AlphaIntelligencePlatform()

    def evaluator(strategy_id: str, parameters: dict[str, object]) -> AlphaCandidate:
        return _candidate(strategy_id, parameters, good=parameters["window"] == 20)

    result = platform.discover(
        "trend",
        "dataset-1",
        {"window": (10, 20, 30)},
        evaluator,
    )
    assert len(result.candidates) == 3
    assert result.champion is not None
    assert result.champion.parameters["window"] == 20
    assert len(platform.catalog.list()) == 3


def test_platform_returns_no_champion_when_all_fail() -> None:
    platform = AlphaIntelligencePlatform()

    def evaluator(strategy_id: str, parameters: dict[str, object]) -> AlphaCandidate:
        return _candidate(strategy_id, parameters, good=False)

    result = platform.discover("weak", "dataset", {"x": (1, 2)}, evaluator)
    assert result.champion is None
