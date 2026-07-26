from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompositeAlphaConfig:
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "momentum": 0.30,
            "trend": 0.25,
            "low_volatility": 0.15,
            "liquidity": 0.10,
            "mean_reversion": 0.10,
            "data_quality": 0.10,
        }
    )
    minimum_factors: int = 3

    def __post_init__(self) -> None:
        if self.minimum_factors < 1:
            raise ValueError("minimum_factors must be positive")
        if not self.weights:
            raise ValueError("At least one alpha weight is required")
        for factor, weight in self.weights.items():
            if not factor or not math.isfinite(weight) or weight == 0.0:
                raise ValueError(
                    "Alpha weights require non-empty factors and finite non-zero weights"
                )


def compute_composite_alpha(
    normalized_scores: Mapping[str, Mapping[str, float | None]],
    config: CompositeAlphaConfig | None = None,
) -> dict[str, float | None]:
    selected = config or CompositeAlphaConfig()
    output: dict[str, float | None] = {}
    for asset, factors in normalized_scores.items():
        weighted_total = 0.0
        absolute_weight = 0.0
        available = 0
        for name, weight in selected.weights.items():
            value = factors.get(name)
            if value is None or not math.isfinite(value):
                continue
            weighted_total += value * weight
            absolute_weight += abs(weight)
            available += 1
        output[asset] = (
            weighted_total / absolute_weight
            if available >= selected.minimum_factors and absolute_weight > 0.0
            else None
        )
    return output


def rank_alpha(alpha_scores: Mapping[str, float | None]) -> list[tuple[str, float]]:
    return sorted(
        ((asset, score) for asset, score in alpha_scores.items() if score is not None),
        key=lambda item: (-item[1], item[0]),
    )
