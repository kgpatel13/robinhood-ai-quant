from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RankingConfig:
    minimum_alpha: float | None = None
    top_n: int = 25
    bottom_n: int = 10
    confidence_high_percentile: float = 0.90
    confidence_medium_percentile: float = 0.70

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be positive")
        if self.bottom_n < 0:
            raise ValueError("bottom_n must be non-negative")
        if not 0.0 <= self.confidence_medium_percentile <= 1.0:
            raise ValueError("confidence_medium_percentile must be within [0, 1]")
        if not 0.0 <= self.confidence_high_percentile <= 1.0:
            raise ValueError("confidence_high_percentile must be within [0, 1]")
        if self.confidence_medium_percentile > self.confidence_high_percentile:
            raise ValueError("medium confidence threshold cannot exceed high threshold")


@dataclass(frozen=True)
class RankedAsset:
    rank: int
    asset_id: str
    symbol: str
    asset_class: str
    timestamp: str
    alpha_score: float
    alpha_percentile: float
    confidence: str
    factor_scores: Mapping[str, float | None]
    factor_coverage: int


def percentile_positions(values: Sequence[float]) -> list[float]:
    """Return stable percentile positions in ascending score order."""
    if not values:
        return []
    if len(values) == 1:
        return [1.0]
    return [index / (len(values) - 1) for index in range(len(values))]


def confidence_label(percentile: float, config: RankingConfig) -> str:
    if percentile >= config.confidence_high_percentile:
        return "high"
    if percentile >= config.confidence_medium_percentile:
        return "medium"
    return "low"


def finite_score(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None
