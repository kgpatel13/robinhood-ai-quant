from __future__ import annotations

from src.atlas.factors.composite import CompositeAlphaConfig, compute_composite_alpha, rank_alpha
from src.atlas.factors.core import FactorRegistry, NormalizationMethod
from src.atlas.factors.defaults import build_default_registry
from src.atlas.factors.diagnostics import factor_correlations, factor_statistics
from src.atlas.factors.engine import FactorEngine, FactorEngineConfig, FactorEngineResult

FACTOR_SET_VERSION = "3.0.0"

__all__ = [
    "FACTOR_SET_VERSION",
    "CompositeAlphaConfig",
    "FactorEngine",
    "FactorEngineConfig",
    "FactorEngineResult",
    "FactorRegistry",
    "NormalizationMethod",
    "build_default_registry",
    "compute_composite_alpha",
    "factor_correlations",
    "factor_statistics",
    "rank_alpha",
]
