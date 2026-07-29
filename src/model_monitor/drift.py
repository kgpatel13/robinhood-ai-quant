from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DriftResult:
    score: float
    threshold: float

    @property
    def drifted(self) -> bool:
        return self.score >= self.threshold


def population_stability_index(
    reference: pd.Series,
    current: pd.Series,
    *,
    bins: int = 10,
    threshold: float = 0.2,
) -> DriftResult:
    if bins < 2:
        raise ValueError("bins must be at least two")
    reference_values = pd.to_numeric(reference, errors="coerce").dropna().to_numpy(dtype=float)
    current_values = pd.to_numeric(current, errors="coerce").dropna().to_numpy(dtype=float)
    if len(reference_values) < bins or len(current_values) < bins:
        return DriftResult(0.0, threshold)
    boundaries = np.unique(np.quantile(reference_values, np.linspace(0.0, 1.0, bins + 1)))
    if len(boundaries) < 3:
        return DriftResult(0.0, threshold)
    boundaries[0] = -np.inf
    boundaries[-1] = np.inf
    reference_counts, _ = np.histogram(reference_values, bins=boundaries)
    current_counts, _ = np.histogram(current_values, bins=boundaries)
    epsilon = 1e-6
    reference_percent = np.maximum(reference_counts / reference_counts.sum(), epsilon)
    current_percent = np.maximum(current_counts / current_counts.sum(), epsilon)
    score = float(
        np.sum((current_percent - reference_percent) * np.log(current_percent / reference_percent))
    )
    return DriftResult(score, threshold)
