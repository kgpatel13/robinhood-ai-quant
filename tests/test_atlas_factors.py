from __future__ import annotations

import math

import pytest

from src.atlas.factors import (
    CompositeAlphaConfig,
    FactorEngine,
    build_default_registry,
    compute_composite_alpha,
    factor_correlations,
    factor_statistics,
    rank_alpha,
)
from src.atlas.factors.normalization import percentile_rank, winsorize, zscore


def _row(scale: float, *, complete: bool = True) -> dict[str, float | None]:
    row: dict[str, float | None] = {
        "return_5d": 0.01 * scale,
        "return_20d": 0.03 * scale,
        "return_60d": 0.08 * scale,
        "return_120d": 0.12 * scale,
        "return_252d": 0.20 * scale,
        "price_to_sma_20": 0.02 * scale,
        "price_to_sma_50": 0.03 * scale,
        "price_to_sma_100": 0.04 * scale,
        "price_to_sma_200": 0.05 * scale,
        "trend_persistence_20": 0.5 + 0.05 * scale,
        "trend_persistence_60": 0.5 + 0.03 * scale,
        "volatility_20d": 0.40 / scale,
        "volatility_60d": 0.35 / scale,
        "volatility_120d": 0.30 / scale,
        "atr_pct_20": 0.04 / scale,
        "bollinger_width_20": 0.20 / scale,
        "average_dollar_volume_20d": 1_000_000.0 * scale,
        "average_dollar_volume_60d": 900_000.0 * scale,
        "relative_volume_20d": 1.0 + 0.1 * scale,
        "money_flow_ratio_20": 0.45 + 0.05 * scale,
        "rsi_14": 70.0 - 10.0 * scale,
        "stochastic_20": 80.0 - 10.0 * scale,
        "bollinger_z_20": 2.0 - scale,
        "distance_from_high_20": -0.02 * scale,
        "bar_count": 300.0 * scale,
        "zero_volume_ratio_60": 0.02 / scale,
        "gap_ratio_60": 0.01 / scale,
    }
    if not complete:
        row["return_120d"] = None
        row["return_252d"] = None
        row["price_to_sma_200"] = None
    return row


def test_normalization_handles_ties_missing_and_outliers() -> None:
    values = {"a": 1.0, "b": 2.0, "c": 2.0, "d": 100.0, "e": None}
    clipped = winsorize(values, 0.0, 0.75)
    assert clipped["d"] == pytest.approx(26.5)
    ranks = percentile_rank(values)
    assert ranks["b"] == ranks["c"]
    assert ranks["e"] is None
    standardized = zscore({"a": 4.0, "b": 4.0, "c": None})
    assert standardized == {"a": 0.0, "b": 0.0, "c": None}


def test_factor_engine_computes_cross_sectional_scores() -> None:
    engine = FactorEngine(build_default_registry())
    result = engine.compute({"AAA": _row(1.0), "BBB": _row(2.0), "CCC": _row(3.0, complete=False)})
    assert set(result.normalized_scores["AAA"]) == {
        "data_quality",
        "liquidity",
        "low_volatility",
        "mean_reversion",
        "momentum",
        "trend",
    }
    assert result.normalized_scores["CCC"]["liquidity"] is not None
    assert result.component_coverage["CCC"]["momentum"] == 3
    assert all(
        value is None or math.isfinite(value)
        for row in result.normalized_scores.values()
        for value in row.values()
    )


def test_composite_alpha_ranking_and_diagnostics() -> None:
    engine = FactorEngine(build_default_registry())
    result = engine.compute({"AAA": _row(1.0), "BBB": _row(2.0), "CCC": _row(3.0)})
    alpha = compute_composite_alpha(
        result.normalized_scores,
        CompositeAlphaConfig(minimum_factors=4),
    )
    ranking = rank_alpha(alpha)
    assert len(ranking) == 3
    assert ranking[0][1] >= ranking[-1][1]
    statistics = factor_statistics(result.normalized_scores)
    assert statistics["momentum"].coverage == 1.0
    correlations = factor_correlations(result.normalized_scores)
    assert correlations["momentum"]["momentum"] == pytest.approx(1.0)


def test_registry_rejects_unknown_factor() -> None:
    registry = build_default_registry()
    with pytest.raises(KeyError, match="Unknown factor"):
        registry.get("not-real")
