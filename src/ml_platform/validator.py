from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from src.ml_platform.models import ClassificationModel, ModelKind


@dataclass(frozen=True)
class ValidationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float


@dataclass(frozen=True)
class WalkForwardResult:
    folds: tuple[ValidationMetrics, ...]

    @property
    def mean_roc_auc(self) -> float:
        return float(np.mean([fold.roc_auc for fold in self.folds]))


class TimeSeriesValidator:
    def __init__(self, splits: int = 5) -> None:
        if splits < 2:
            raise ValueError("splits must be at least two")
        self.splits = splits

    def evaluate(
        self,
        kind: ModelKind,
        features: pd.DataFrame,
        target: pd.Series,
        *,
        random_state: int = 42,
    ) -> WalkForwardResult:
        folds: list[ValidationMetrics] = []
        for train_index, test_index in TimeSeriesSplit(n_splits=self.splits).split(features):
            model = ClassificationModel(kind, random_state=random_state)
            model.fit(features.iloc[train_index], target.iloc[train_index])
            result = model.predict(features.iloc[test_index])
            truth = target.iloc[test_index]
            positive_probability = result.probabilities[:, 1]
            try:
                roc_auc = float(roc_auc_score(truth, positive_probability))
            except ValueError:
                roc_auc = 0.5
            folds.append(
                ValidationMetrics(
                    accuracy=float(accuracy_score(truth, result.labels)),
                    precision=float(precision_score(truth, result.labels, zero_division=0)),
                    recall=float(recall_score(truth, result.labels, zero_division=0)),
                    f1=float(f1_score(truth, result.labels, zero_division=0)),
                    roc_auc=roc_auc,
                )
            )
        return WalkForwardResult(tuple(folds))
