from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.ml_platform import (
    AutomatedTrainingPipeline,
    FeatureSetDefinition,
    ModelRegistry,
    ModelStage,
    OfflineFeatureStore,
    PopulationStabilityDriftDetector,
    PromotionPolicy,
)


def test_feature_store_supports_point_in_time_reads(tmp_path) -> None:
    definition = FeatureSetDefinition(
        name="equity_technical",
        version="1",
        entity_keys=("symbol",),
        timestamp_column="timestamp",
        feature_columns=("momentum", "volatility"),
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    frame = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
            "timestamp": [start, start + timedelta(days=1), start, start + timedelta(days=1)],
            "momentum": [0.1, 0.2, -0.1, 0.3],
            "volatility": [0.2, 0.25, 0.3, 0.28],
        }
    )
    store = OfflineFeatureStore(tmp_path)
    snapshot = store.write(definition, frame)
    latest = store.latest_by_entity(definition, as_of=start)
    assert snapshot.rows == 4
    assert len(latest) == 2
    assert set(latest["symbol"]) == {"AAPL", "MSFT"}


def test_model_registry_promotes_and_rolls_back(tmp_path) -> None:
    registry = ModelRegistry(tmp_path)
    registry.register(
        name="direction",
        version="v1",
        model={"value": 1},
        metrics={"mean_roc_auc": 0.60},
        feature_set="equity:1",
    )
    registry.promote("direction", "v1")
    registry.register(
        name="direction",
        version="v2",
        model={"value": 2},
        metrics={"mean_roc_auc": 0.65},
        feature_set="equity:1",
    )
    registry.promote("direction", "v2")
    assert registry.get("direction", "v1").stage is ModelStage.ARCHIVED
    assert registry.champion("direction").version == "v2"  # type: ignore[union-attr]
    registry.rollback("direction", "v1")
    assert registry.champion("direction").version == "v1"  # type: ignore[union-attr]


def test_drift_detector_flags_distribution_shift() -> None:
    generator = np.random.default_rng(7)
    reference = pd.DataFrame({"feature": generator.normal(0, 1, 500)})
    current = pd.DataFrame({"feature": generator.normal(3, 1, 500)})
    report = PopulationStabilityDriftDetector(threshold=0.2).compare(reference, current)
    assert report.drift_detected
    assert "feature" in report.drifted_features


def test_automated_training_registers_and_promotes_candidate(tmp_path) -> None:
    generator = np.random.default_rng(42)
    rows = 240
    feature_a = generator.normal(size=rows)
    feature_b = generator.normal(size=rows)
    target = pd.Series((feature_a + feature_b * 0.25 > 0).astype(int))
    features = pd.DataFrame({"feature_a": feature_a, "feature_b": feature_b})
    registry = ModelRegistry(tmp_path)
    pipeline = AutomatedTrainingPipeline(
        registry,
        promotion_policy=PromotionPolicy(minimum_score=0.5, minimum_improvement=0.0),
        clock=lambda: datetime(2026, 7, 28, 20, 0, tzinfo=UTC),
    )
    run = pipeline.run(
        model_name="direction",
        feature_set="equity_technical:1",
        features=features,
        target=target,
        search_space={
            "model_type": ("logistic_regression", "random_forest"),
            "splits": (3,),
            "minimum_rows": (100,),
        },
    )
    assert run.promoted
    assert run.registered_model.stage is ModelStage.CHAMPION
    assert registry.champion("direction") is not None
