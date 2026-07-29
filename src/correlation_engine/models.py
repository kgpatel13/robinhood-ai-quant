from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorrelationPolicy:
    lookback: int = 60
    high_correlation_threshold: float = 0.80
    maximum_cluster_weight: float = 0.35
    maximum_sector_weight: float = 0.30


@dataclass(frozen=True)
class CorrelatedPair:
    left: str
    right: str
    correlation: float


@dataclass(frozen=True)
class DiversificationReport:
    correlation_matrix: dict[str, dict[str, float]]
    highly_correlated_pairs: tuple[CorrelatedPair, ...]
    cluster_weights: dict[int, float]
    sector_weights: dict[str, float]
    diversification_score: float
    warnings: tuple[str, ...]
