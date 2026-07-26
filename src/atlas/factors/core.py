from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

FeatureRow = Mapping[str, float | None]
FactorValue = float | None


class NormalizationMethod(StrEnum):
    ZSCORE = "zscore"
    PERCENTILE = "percentile"


@dataclass(frozen=True)
class FactorComponent:
    feature: str
    weight: float = 1.0
    direction: int = 1

    def __post_init__(self) -> None:
        if not self.feature:
            raise ValueError("Factor component feature must not be empty")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("Factor component weight must be finite and positive")
        if self.direction not in (-1, 1):
            raise ValueError("Factor component direction must be -1 or 1")


@dataclass(frozen=True)
class FactorMetadata:
    name: str
    category: str
    description: str
    components: tuple[FactorComponent, ...]
    normalization: NormalizationMethod = NormalizationMethod.ZSCORE
    minimum_components: int = 1

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Factor name must not be empty")
        if not self.components:
            raise ValueError(f"Factor {self.name} requires at least one component")
        if not 1 <= self.minimum_components <= len(self.components):
            raise ValueError("minimum_components must be within component count")


@dataclass(frozen=True)
class FactorDefinition:
    metadata: FactorMetadata


class FactorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, FactorDefinition] = {}

    def register(self, definition: FactorDefinition) -> None:
        name = definition.metadata.name
        if name in self._definitions:
            raise ValueError(f"Factor already registered: {name}")
        self._definitions[name] = definition

    def definitions(self) -> tuple[FactorDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def get(self, name: str) -> FactorDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"Unknown factor: {name}") from exc

    def metadata_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.metadata.name,
                "category": item.metadata.category,
                "description": item.metadata.description,
                "normalization": item.metadata.normalization.value,
                "minimum_components": item.metadata.minimum_components,
                "components": [
                    {
                        "feature": component.feature,
                        "weight": component.weight,
                        "direction": component.direction,
                    }
                    for component in item.metadata.components
                ],
            }
            for item in self.definitions()
        ]


def finite_feature_value(row: FeatureRow, feature: str) -> float | None:
    value = row.get(feature)
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def ensure_unique_assets(rows: Mapping[str, FeatureRow] | Sequence[tuple[str, FeatureRow]]) -> None:
    if isinstance(rows, Mapping):
        return
    assets = [asset for asset, _ in rows]
    if len(assets) != len(set(assets)):
        raise ValueError("Asset identifiers must be unique")
