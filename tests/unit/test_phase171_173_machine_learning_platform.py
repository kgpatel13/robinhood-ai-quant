from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.feature_store import (
    FeatureMetadata,
    FeatureNormalizer,
    FeatureRegistry,
    MarketFeatureBuilder,
)
from src.ml_platform import ClassificationModel, ModelKind, TimeSeriesValidator
from src.model_monitor import ModelMonitor, MonitoringPolicy, population_stability_index


def market_frame(rows: int = 80) -> pd.DataFrame:
    close = np.linspace(100.0, 120.0, rows) + np.sin(np.arange(rows))
    return pd.DataFrame(
        {
            "close": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "volume": np.linspace(1_000.0, 2_000.0, rows),
        }
    )


def classification_data(rows: int = 120) -> tuple[pd.DataFrame, pd.Series]:
    first = np.linspace(-2.0, 2.0, rows)
    second = np.cos(np.arange(rows) / 5.0)
    features = pd.DataFrame({"first": first, "second": second})
    target = pd.Series(((np.arange(rows) % 3) == 0).astype(int))
    return features, target


def test_feature_builder_creates_versioned_features() -> None:
    builder = MarketFeatureBuilder(metadata=FeatureMetadata("prices", "2"))
    result = builder.build(market_frame())
    assert result.attrs["feature_set"] == "prices:2"
    assert {"rsi", "atr", "macd", "relative_volume"}.issubset(result.columns)


def test_feature_builder_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing market columns"):
        MarketFeatureBuilder().build(pd.DataFrame({"close": [1.0]}))


def test_feature_clean_removes_missing_and_infinite_values() -> None:
    frame = pd.DataFrame({"a": [1.0, np.inf], "b": [np.nan, 2.0]})
    clean = MarketFeatureBuilder.clean(frame)
    assert np.isfinite(clean.to_numpy()).all()


def test_feature_normalizer_preserves_shape_and_columns() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]})
    normalizer = FeatureNormalizer()
    normalized = normalizer.fit_transform(frame)
    assert normalized.shape == frame.shape
    assert list(normalized.columns) == ["a", "b"]


def test_feature_normalizer_rejects_column_mismatch() -> None:
    normalizer = FeatureNormalizer()
    normalizer.fit_transform(pd.DataFrame({"a": [1.0, 2.0]}))
    with pytest.raises(ValueError, match="do not match"):
        normalizer.transform(pd.DataFrame({"b": [1.0, 2.0]}))


def test_feature_registry_round_trip() -> None:
    registry = FeatureRegistry()
    metadata = FeatureMetadata("technical", "1")
    registry.register(metadata)
    assert registry.get("technical:1") == metadata
    assert registry.list_all() == (metadata,)


def test_feature_registry_rejects_duplicate() -> None:
    registry = FeatureRegistry()
    registry.register(FeatureMetadata("technical", "1"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FeatureMetadata("technical", "1"))


@pytest.mark.parametrize("kind", list(ModelKind))
def test_classification_models_train_and_predict(kind: ModelKind) -> None:
    features, target = classification_data()
    model = ClassificationModel(kind, version="model-v1").fit(features, target)
    prediction = model.predict(features.tail(10))
    assert prediction.labels.shape == (10,)
    assert prediction.probabilities.shape == (10, 2)
    assert prediction.model_version == "model-v1"
    assert np.all((prediction.confidence >= 0.5) & (prediction.confidence <= 1.0))


def test_feature_importance_is_normalized() -> None:
    features, target = classification_data()
    model = ClassificationModel(ModelKind.RANDOM_FOREST).fit(features, target)
    importance = model.feature_importance()
    assert set(importance) == set(features.columns)
    assert sum(importance.values()) == pytest.approx(1.0)


def test_prediction_rejects_different_features() -> None:
    features, target = classification_data()
    model = ClassificationModel(ModelKind.LOGISTIC_REGRESSION).fit(features, target)
    with pytest.raises(ValueError, match="do not match"):
        model.predict(features.rename(columns={"first": "changed"}))


def test_time_series_validator_returns_fold_metrics() -> None:
    features, target = classification_data()
    result = TimeSeriesValidator(splits=3).evaluate(
        ModelKind.LOGISTIC_REGRESSION,
        features,
        target,
    )
    assert len(result.folds) == 3
    assert 0.0 <= result.mean_roc_auc <= 1.0


def test_population_stability_index_detects_large_shift() -> None:
    reference = pd.Series(np.linspace(0.0, 1.0, 200))
    current = pd.Series(np.linspace(5.0, 6.0, 200))
    assert population_stability_index(reference, current).drifted


def test_model_monitor_recommends_retraining_for_drift() -> None:
    monitor = ModelMonitor(MonitoringPolicy(minimum_roc_auc=0.4, drift_threshold=0.1))
    report = monitor.evaluate(
        truth=np.asarray([0, 1, 0, 1], dtype=np.int_),
        labels=np.asarray([0, 1, 0, 1], dtype=np.int_),
        probabilities=np.asarray(
            [[0.9, 0.1], [0.1, 0.9], [0.8, 0.2], [0.2, 0.8]],
            dtype=np.float64,
        ),
        reference_features=pd.DataFrame({"feature": np.linspace(0.0, 1.0, 100)}),
        current_features=pd.DataFrame({"feature": np.linspace(5.0, 6.0, 100)}),
        reference_probabilities=pd.Series(np.linspace(0.0, 0.4, 100)),
    )
    assert report.retraining_recommended
    assert "feature_drift" in report.reasons
