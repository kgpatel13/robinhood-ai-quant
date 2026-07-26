from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from src.atlas.factors.core import (
    FactorRegistry,
    FeatureRow,
    NormalizationMethod,
    finite_feature_value,
)
from src.atlas.factors.normalization import percentile_rank, winsorize, zscore


@dataclass(frozen=True)
class FactorEngineConfig:
    winsor_lower: float = 0.025
    winsor_upper: float = 0.975
    minimum_cross_section: int = 2


@dataclass(frozen=True)
class FactorEngineResult:
    raw_scores: dict[str, dict[str, float | None]]
    normalized_scores: dict[str, dict[str, float | None]]
    component_coverage: dict[str, dict[str, int]]


class FactorEngine:
    def __init__(self, registry: FactorRegistry, config: FactorEngineConfig | None = None) -> None:
        self._registry = registry
        self._config = config or FactorEngineConfig()
        if self._config.minimum_cross_section < 1:
            raise ValueError("minimum_cross_section must be positive")

    def compute(self, features_by_asset: Mapping[str, FeatureRow]) -> FactorEngineResult:
        raw: dict[str, dict[str, float | None]] = {asset: {} for asset in features_by_asset}
        normalized: dict[str, dict[str, float | None]] = {asset: {} for asset in features_by_asset}
        coverage: dict[str, dict[str, int]] = {asset: {} for asset in features_by_asset}

        for definition in self._registry.definitions():
            metadata = definition.metadata
            factor_values: dict[str, float | None] = {}
            for asset, row in features_by_asset.items():
                weighted_total = 0.0
                weight_total = 0.0
                available = 0
                for component in metadata.components:
                    value = finite_feature_value(row, component.feature)
                    if value is None:
                        continue
                    weighted_total += value * component.weight * component.direction
                    weight_total += component.weight
                    available += 1
                score = (
                    weighted_total / weight_total
                    if available >= metadata.minimum_components and weight_total > 0.0
                    else None
                )
                factor_values[asset] = score if score is None or math.isfinite(score) else None
                raw[asset][metadata.name] = factor_values[asset]
                coverage[asset][metadata.name] = available

            finite_count = sum(value is not None for value in factor_values.values())
            if finite_count < self._config.minimum_cross_section:
                normalized_values: dict[str, float | None] = {
                    asset: None for asset in factor_values
                }
            else:
                clipped = winsorize(
                    factor_values,
                    lower=self._config.winsor_lower,
                    upper=self._config.winsor_upper,
                )
                normalized_values = (
                    percentile_rank(clipped)
                    if metadata.normalization is NormalizationMethod.PERCENTILE
                    else zscore(clipped)
                )
            for asset, value in normalized_values.items():
                normalized[asset][metadata.name] = value

        return FactorEngineResult(
            raw_scores=raw,
            normalized_scores=normalized,
            component_coverage=coverage,
        )
