from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from src.execution_costs import (
    AssetClass,
    ExecutionCostRequest,
    ExecutionCostSimulator,
    TradingHorizon,
    default_profile,
)
from src.feature_intelligence import FeatureDiagnostics
from src.strategy_intelligence import (
    StrategyGrade,
    StrategyMetrics,
    StrategyRanker,
)


def test_feature_diagnostics_finds_signal_and_redundancy() -> None:
    rng = np.random.default_rng(42)
    signal = rng.normal(size=200)
    noise = rng.normal(size=200)
    features = pd.DataFrame({"signal": signal, "copy": signal * 1.01, "noise": noise})
    target = pd.Series((signal > 0).astype(int))
    model = LogisticRegression().fit(features, target)

    report = FeatureDiagnostics(correlation_threshold=0.95).analyze(
        model=model, features=features, target=target, repeats=3
    )

    assert report.permutation_importance[0].feature in {"signal", "copy"}
    assert report.redundant_pairs[0].correlation > 0.99
    assert {"signal", "copy"} & set(report.prune_candidates)


def test_feature_stability_rewards_consistency() -> None:
    stable = FeatureDiagnostics.stability(
        [{"a": 1.0, "b": 1.0}, {"a": 1.0, "b": -1.0}, {"a": 1.0}]
    )
    assert stable["a"] > stable["b"]


def test_execution_cost_increases_with_participation() -> None:
    simulator = ExecutionCostSimulator()
    profile = default_profile(AssetClass.EQUITY, TradingHorizon.DAY)
    small = simulator.estimate(ExecutionCostRequest(100, 100, 1_000_000), profile)
    large = simulator.estimate(ExecutionCostRequest(100, 100_000, 1_000_000), profile)

    assert large.total_bps > small.total_bps
    assert large.fill_ratio == pytest.approx(1.0)


def test_execution_cost_caps_fill_ratio() -> None:
    simulator = ExecutionCostSimulator()
    profile = default_profile(AssetClass.CRYPTO, TradingHorizon.SCALPING)
    estimate = simulator.estimate(ExecutionCostRequest(10, 100_000, 200_000), profile)
    assert estimate.fill_ratio == pytest.approx(0.1)


def test_strategy_ranker_rejects_weak_out_of_sample_result() -> None:
    score = StrategyRanker().score(
        "overfit",
        StrategyMetrics(
            annual_return=0.4,
            sharpe_ratio=2.0,
            maximum_drawdown=0.1,
            consistency=0.9,
            regime_stability=0.8,
            turnover=2.0,
            execution_cost_bps=5.0,
            prediction_quality=0.8,
            out_of_sample_return=-0.01,
        ),
    )
    assert score.grade is StrategyGrade.REJECTED
    assert not score.deploy_to_paper


def test_strategy_ranker_orders_candidates() -> None:
    ranker = StrategyRanker()
    strong = StrategyMetrics(0.25, 1.8, 0.08, 0.9, 0.9, 1.0, 4.0, 0.85, 0.15)
    moderate = StrategyMetrics(0.12, 1.0, 0.15, 0.7, 0.65, 4.0, 15.0, 0.65, 0.06)
    ranked = ranker.rank({"strong": strong, "moderate": moderate})
    assert ranked[0].name == "strong"
    assert ranked[0].score > ranked[1].score
