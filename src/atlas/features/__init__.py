from __future__ import annotations

from src.atlas.features import momentum, quality, trend, volatility, volume
from src.atlas.features.core import FeatureRegistry

FEATURE_SET_VERSION = "2.5.0"


def build_default_registry() -> FeatureRegistry:
    registry = FeatureRegistry()
    for module in (trend, momentum, volatility, volume, quality):
        module.register(registry)
    return registry


__all__ = ["FEATURE_SET_VERSION", "FeatureRegistry", "build_default_registry"]
