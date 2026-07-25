from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase11.intelligence import (
    deterministic_sample,
    feature_predictiveness,
    feature_recommendations,
    feature_redundancy,
    feature_stability,
    feature_summary,
)
from src.research.phase11.intelligence_models import FeatureIntelligenceConfig


def _dataset(rows: int = 500) -> pd.DataFrame:
    index = np.arange(rows, dtype=float)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=rows, freq="D", tz="UTC"),
            "symbol": np.where(index % 2 == 0, "AAA", "BBB"),
            "asset_class": np.where(index % 3 == 0, "crypto", "stock"),
            "holding_period": np.where(index % 2 == 0, 5, 10),
            "regime": np.where(index % 3 == 0, "risk_on", "neutral"),
            "net_forward_return": (index % 17 - 8) / 1_000.0,
            "positive_return_label": ((index % 17 - 8) > 0).astype(int),
        }
    )
    for position, feature in enumerate(FEATURE_COLUMNS):
        frame[feature] = np.sin(index / (position + 2)) + position * 0.01
    frame["ema_50_distance"] = frame["ema_20_distance"] * 0.999
    return frame


def test_deterministic_sample_is_repeatable() -> None:
    frame = _dataset()
    first = deterministic_sample(frame, 100)
    second = deterministic_sample(frame, 100)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 100


def test_feature_summary_and_predictiveness_cover_every_feature() -> None:
    frame = _dataset()
    summary = feature_summary(frame)
    predictive = feature_predictiveness(
        frame,
        "net_forward_return",
        "positive_return_label",
    )
    assert set(summary["feature"]) == set(FEATURE_COLUMNS)
    assert set(predictive["feature"]) == set(FEATURE_COLUMNS)


def test_redundancy_detects_highly_correlated_features() -> None:
    redundancy = feature_redundancy(_dataset(), 0.95)
    pairs = set(zip(redundancy["feature_a"], redundancy["feature_b"], strict=False))
    assert ("ema_20_distance", "ema_50_distance") in pairs


def test_recommendations_are_created_for_every_feature() -> None:
    frame = _dataset()
    config = FeatureIntelligenceConfig(maximum_analysis_rows=1_000)
    summary = feature_summary(frame)
    outliers = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "outlier_fraction": [0.0] * len(FEATURE_COLUMNS),
        }
    )
    predictive = feature_predictiveness(
        frame,
        config.target_column,
        config.classification_target,
    )
    stability = feature_stability(frame, config.target_column)
    recommendations = feature_recommendations(
        summary,
        outliers,
        predictive,
        stability,
        pd.DataFrame(),
        feature_redundancy(frame, config.correlation_threshold),
        config,
    )
    assert len(recommendations) == len(FEATURE_COLUMNS)
    assert set(recommendations["recommendation"]) <= {
        "KEEP",
        "KEEP_WITH_WINSORIZATION",
        "REVIEW",
        "REMOVE",
    }
