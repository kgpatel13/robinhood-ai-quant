from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from src.correlation_engine.models import (
    CorrelatedPair,
    CorrelationPolicy,
    DiversificationReport,
)


class CorrelationEngine:
    """Measures dependence, clusters exposures, and reports concentration risk."""

    def analyze(
        self,
        returns: pd.DataFrame,
        weights: dict[str, float],
        sectors: dict[str, str] | None = None,
        policy: CorrelationPolicy | None = None,
    ) -> DiversificationReport:
        selected = policy or CorrelationPolicy()
        if selected.lookback < 2:
            raise ValueError("lookback must be at least 2")
        names = [str(column) for column in returns.columns]
        if not names:
            raise ValueError("returns must contain assets")
        missing = set(weights) - set(names)
        if missing:
            raise ValueError(f"weights contain unknown assets: {sorted(missing)}")
        recent = returns.tail(selected.lookback).dropna(how="any")
        if len(recent) < 2:
            raise ValueError("insufficient complete return observations")
        correlation = recent.corr().clip(-1.0, 1.0)
        pairs = self._high_pairs(correlation, selected.high_correlation_threshold)
        labels = self._cluster_labels(correlation, selected.high_correlation_threshold)
        cluster_weights: dict[int, float] = {}
        for name, cluster in zip(names, labels, strict=True):
            cluster_weights[int(cluster)] = cluster_weights.get(int(cluster), 0.0) + weights.get(
                name,
                0.0,
            )
        sector_weights: dict[str, float] = {}
        for name, weight in weights.items():
            sector = (sectors or {}).get(name, "UNCLASSIFIED")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        warnings: list[str] = []
        for cluster, weight in sorted(cluster_weights.items()):
            if weight > selected.maximum_cluster_weight:
                warnings.append(f"cluster_{cluster}_weight_exceeds_limit")
        for sector, weight in sorted(sector_weights.items()):
            if weight > selected.maximum_sector_weight:
                warnings.append(f"sector_{sector}_weight_exceeds_limit")
        weighted_average = self._weighted_average_correlation(correlation, weights)
        score = max(0.0, min(100.0, 100.0 * (1.0 - weighted_average)))
        matrix = {
            row: {column: float(cast(float, correlation.at[row, column])) for column in names}
            for row in names
        }
        return DiversificationReport(
            correlation_matrix=matrix,
            highly_correlated_pairs=tuple(pairs),
            cluster_weights=cluster_weights,
            sector_weights=sector_weights,
            diversification_score=score,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _high_pairs(
        correlation: pd.DataFrame,
        threshold: float,
    ) -> list[CorrelatedPair]:
        names = [str(column) for column in correlation.columns]
        result: list[CorrelatedPair] = []
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                value = float(cast(float, correlation.at[left, right]))
                if abs(value) >= threshold:
                    result.append(CorrelatedPair(left, right, value))
        return result

    @staticmethod
    def _cluster_labels(correlation: pd.DataFrame, threshold: float) -> np.ndarray:
        if len(correlation) == 1:
            return np.asarray([1], dtype=int)
        distance = np.sqrt(np.clip((1.0 - np.asarray(correlation, dtype=float)) / 2.0, 0.0, 1.0))
        condensed = squareform(distance, checks=False)
        hierarchy = linkage(condensed, method="average")
        cutoff = np.sqrt(max(0.0, (1.0 - threshold) / 2.0))
        return np.asarray(fcluster(hierarchy, t=cutoff, criterion="distance"), dtype=int)

    @staticmethod
    def _weighted_average_correlation(
        correlation: pd.DataFrame,
        weights: dict[str, float],
    ) -> float:
        names = [str(column) for column in correlation.columns]
        numerator = 0.0
        denominator = 0.0
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                pair_weight = abs(weights.get(left, 0.0) * weights.get(right, 0.0))
                numerator += pair_weight * abs(float(cast(float, correlation.at[left, right])))
                denominator += pair_weight
        return numerator / denominator if denominator else 0.0
