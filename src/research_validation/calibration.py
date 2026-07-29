from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss


class CalibrationMethod(StrEnum):
    SIGMOID = "sigmoid"
    ISOTONIC = "isotonic"


@dataclass(frozen=True)
class CalibrationMetrics:
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    maximum_calibration_error: float
    observations: int


class ProbabilityCalibrator:
    """Calibrate binary probabilities without retraining the underlying model."""

    def __init__(self, method: CalibrationMethod = CalibrationMethod.SIGMOID) -> None:
        self.method = method
        self._model: LogisticRegression | IsotonicRegression | None = None

    def fit(self, probabilities: np.ndarray[Any, Any], target: np.ndarray[Any, Any]) -> None:
        x, y = self._validate(probabilities, target)
        if self.method is CalibrationMethod.ISOTONIC:
            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(x, y)
            self._model = model
            return
        model = LogisticRegression(max_iter=2_000)
        model.fit(x.reshape(-1, 1), y)
        self._model = model

    def transform(self, probabilities: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        if self._model is None:
            raise RuntimeError("calibrator must be fitted before transform")
        values = self._probabilities(probabilities)
        if isinstance(self._model, IsotonicRegression):
            calibrated = self._model.predict(values)
        else:
            calibrated = self._model.predict_proba(values.reshape(-1, 1))[:, 1]
        return np.clip(np.asarray(calibrated, dtype=float), 0.0, 1.0)

    @staticmethod
    def evaluate(
        probabilities: np.ndarray[Any, Any],
        target: np.ndarray[Any, Any],
        *,
        bins: int = 10,
    ) -> CalibrationMetrics:
        if bins < 2:
            raise ValueError("bins must be at least two")
        values, y = ProbabilityCalibrator._validate(probabilities, target)
        clipped = np.clip(values, 1e-12, 1 - 1e-12)
        edges = np.linspace(0.0, 1.0, bins + 1)
        bucket_ids = np.minimum(np.digitize(values, edges[1:-1]), bins - 1)
        weighted_error = 0.0
        maximum_error = 0.0
        for bucket in range(bins):
            mask = bucket_ids == bucket
            count = int(mask.sum())
            if count == 0:
                continue
            gap = abs(float(values[mask].mean()) - float(y[mask].mean()))
            weighted_error += gap * count / len(values)
            maximum_error = max(maximum_error, gap)
        return CalibrationMetrics(
            brier_score=float(brier_score_loss(y, values)),
            log_loss=float(log_loss(y, clipped, labels=[0, 1])),
            expected_calibration_error=weighted_error,
            maximum_calibration_error=maximum_error,
            observations=len(values),
        )

    @staticmethod
    def _validate(
        probabilities: np.ndarray[Any, Any], target: np.ndarray[Any, Any]
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        values = ProbabilityCalibrator._probabilities(probabilities)
        y = np.asarray(target, dtype=int).reshape(-1)
        if len(values) != len(y):
            raise ValueError("probabilities and target must have equal length")
        if len(values) == 0:
            raise ValueError("at least one observation is required")
        if not set(np.unique(y)).issubset({0, 1}):
            raise ValueError("target must contain binary values 0 and 1")
        return values, y

    @staticmethod
    def _probabilities(probabilities: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        values = np.asarray(probabilities, dtype=float).reshape(-1)
        if not np.isfinite(values).all():
            raise ValueError("probabilities must be finite")
        if ((values < 0.0) | (values > 1.0)).any():
            raise ValueError("probabilities must be between zero and one")
        return values
