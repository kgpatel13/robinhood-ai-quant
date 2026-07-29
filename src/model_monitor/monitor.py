from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from src.model_monitor.drift import DriftResult, population_stability_index
from src.model_monitor.metrics import ClassificationMetrics, classification_metrics


@dataclass(frozen=True)
class MonitoringPolicy:
    minimum_roc_auc: float = 0.55
    maximum_calibration_error: float = 0.35
    drift_threshold: float = 0.2


@dataclass(frozen=True)
class ModelHealthReport:
    metrics: ClassificationMetrics
    feature_drift: dict[str, DriftResult]
    prediction_drift: DriftResult
    retraining_recommended: bool
    reasons: tuple[str, ...]


class ModelMonitor:
    def __init__(self, policy: MonitoringPolicy | None = None) -> None:
        self.policy = policy or MonitoringPolicy()

    def evaluate(
        self,
        *,
        truth: NDArray[np.int_],
        labels: NDArray[np.int_],
        probabilities: NDArray[np.float64],
        reference_features: pd.DataFrame,
        current_features: pd.DataFrame,
        reference_probabilities: pd.Series,
    ) -> ModelHealthReport:
        positive_probability = probabilities[:, 1]
        metrics = classification_metrics(truth, labels, positive_probability)
        shared = sorted(set(reference_features.columns) & set(current_features.columns))
        feature_drift = {
            column: population_stability_index(
                reference_features[column],
                current_features[column],
                threshold=self.policy.drift_threshold,
            )
            for column in shared
        }
        prediction_drift = population_stability_index(
            reference_probabilities,
            pd.Series(positive_probability),
            threshold=self.policy.drift_threshold,
        )
        reasons: list[str] = []
        if metrics.roc_auc < self.policy.minimum_roc_auc:
            reasons.append("roc_auc_below_threshold")
        if metrics.calibration_error > self.policy.maximum_calibration_error:
            reasons.append("calibration_error_above_threshold")
        if prediction_drift.drifted:
            reasons.append("prediction_drift")
        if any(result.drifted for result in feature_drift.values()):
            reasons.append("feature_drift")
        return ModelHealthReport(
            metrics,
            feature_drift,
            prediction_drift,
            bool(reasons),
            tuple(reasons),
        )
