from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    calibration_error: float


def classification_metrics(
    truth: NDArray[np.int_],
    labels: NDArray[np.int_],
    positive_probability: NDArray[np.float64],
) -> ClassificationMetrics:
    try:
        roc_auc = float(roc_auc_score(truth, positive_probability))
    except ValueError:
        roc_auc = 0.5
    calibration_error = float(np.mean(np.abs(positive_probability - truth)))
    return ClassificationMetrics(
        accuracy=float(accuracy_score(truth, labels)),
        precision=float(precision_score(truth, labels, zero_division=0)),
        recall=float(recall_score(truth, labels, zero_division=0)),
        f1=float(f1_score(truth, labels, zero_division=0)),
        roc_auc=roc_auc,
        calibration_error=calibration_error,
    )
