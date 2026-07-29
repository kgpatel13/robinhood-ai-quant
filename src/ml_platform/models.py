from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression


class ModelKind(StrEnum):
    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"


@dataclass(frozen=True)
class PredictionResult:
    labels: NDArray[np.int_]
    probabilities: NDArray[np.float64]
    confidence: NDArray[np.float64]
    model_version: str


class ClassificationModel:
    def __init__(
        self,
        kind: ModelKind,
        *,
        version: str = "1",
        random_state: int = 42,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.kind = kind
        self.version = version
        self.random_state = random_state
        self.parameters = parameters or {}
        self.estimator = self._create_estimator()
        self.feature_names: tuple[str, ...] = ()

    def fit(self, features: pd.DataFrame, target: pd.Series) -> ClassificationModel:
        if features.empty or target.empty:
            raise ValueError("training data must not be empty")
        if len(features) != len(target):
            raise ValueError("features and target must contain the same number of rows")
        self.feature_names = tuple(features.columns)
        self.estimator.fit(features, target)
        return self

    def predict(self, features: pd.DataFrame) -> PredictionResult:
        self._validate_features(features)
        labels = np.asarray(self.estimator.predict(features), dtype=np.int_)
        probabilities = np.asarray(self.estimator.predict_proba(features), dtype=np.float64)
        confidence = probabilities.max(axis=1)
        return PredictionResult(labels, probabilities, confidence, self.version)

    def feature_importance(self) -> dict[str, float]:
        if not self.feature_names:
            raise RuntimeError("model has not been fitted")
        raw: NDArray[np.float64]
        if hasattr(self.estimator, "feature_importances_"):
            raw = np.asarray(self.estimator.feature_importances_, dtype=np.float64)
        elif hasattr(self.estimator, "coef_"):
            coefficients = np.asarray(self.estimator.coef_, dtype=np.float64)
            raw = np.abs(coefficients).mean(axis=0)
        else:
            raw = np.zeros(len(self.feature_names), dtype=np.float64)
        total = float(raw.sum())
        normalized = raw / total if total > 0 else raw
        return dict(zip(self.feature_names, normalized.tolist(), strict=True))

    def _create_estimator(self) -> Any:
        if self.kind is ModelKind.LOGISTIC_REGRESSION:
            return LogisticRegression(
                max_iter=1_000,
                random_state=self.random_state,
                **self.parameters,
            )
        if self.kind is ModelKind.RANDOM_FOREST:
            return RandomForestClassifier(
                n_estimators=100,
                random_state=self.random_state,
                **self.parameters,
            )
        return GradientBoostingClassifier(random_state=self.random_state, **self.parameters)

    def _validate_features(self, features: pd.DataFrame) -> None:
        if not self.feature_names:
            raise RuntimeError("model has not been fitted")
        if tuple(features.columns) != self.feature_names:
            raise ValueError("prediction features do not match training features")
