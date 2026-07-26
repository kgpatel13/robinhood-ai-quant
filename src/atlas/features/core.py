from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from src.atlas.market_models import PriceBar

FeatureValue = float | None
FeatureFunction = Callable[["FeatureContext"], FeatureValue]


@dataclass(frozen=True)
class FeatureMetadata:
    name: str
    category: str
    description: str
    window: int | None = None
    unit: str = "ratio"
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class FeatureDefinition:
    metadata: FeatureMetadata
    compute: FeatureFunction


@dataclass(frozen=True)
class FeatureContext:
    bars: Sequence[PriceBar]

    @property
    def closes(self) -> list[float]:
        return [bar.close for bar in self.bars]

    @property
    def highs(self) -> list[float]:
        return [bar.high for bar in self.bars]

    @property
    def lows(self) -> list[float]:
        return [bar.low for bar in self.bars]

    @property
    def volumes(self) -> list[float]:
        return [bar.volume for bar in self.bars]


class FeatureRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}

    def register(self, definition: FeatureDefinition) -> None:
        name = definition.metadata.name
        if name in self._definitions:
            raise ValueError(f"Feature already registered: {name}")
        self._definitions[name] = definition

    def definitions(self) -> tuple[FeatureDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def metadata_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.metadata.name,
                "category": item.metadata.category,
                "description": item.metadata.description,
                "window": item.metadata.window,
                "unit": item.metadata.unit,
                "minimum": item.metadata.minimum,
                "maximum": item.metadata.maximum,
            }
            for item in self.definitions()
        ]

    def compute(self, bars: Sequence[PriceBar]) -> dict[str, FeatureValue]:
        context = FeatureContext(bars=bars)
        output: dict[str, FeatureValue] = {}
        for definition in self.definitions():
            value = definition.compute(context)
            if value is not None and not math.isfinite(value):
                value = None
            output[definition.metadata.name] = value
        return output


def register_feature(
    registry: FeatureRegistry,
    *,
    name: str,
    category: str,
    description: str,
    compute: FeatureFunction,
    window: int | None = None,
    unit: str = "ratio",
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    registry.register(
        FeatureDefinition(
            metadata=FeatureMetadata(
                name=name,
                category=category,
                description=description,
                window=window,
                unit=unit,
                minimum=minimum,
                maximum=maximum,
            ),
            compute=compute,
        )
    )
