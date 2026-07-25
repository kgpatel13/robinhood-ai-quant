"""Phase 11 machine-learning dataset and feature-intelligence research."""

from src.research.phase11.engine import build_phase11_dataset
from src.research.phase11.intelligence_engine import run_feature_intelligence
from src.research.phase11.intelligence_models import (
    FeatureIntelligenceConfig,
    FeatureIntelligenceResult,
)
from src.research.phase11.models import Phase11Config, Phase11Result

__all__ = [
    "FeatureIntelligenceConfig",
    "FeatureIntelligenceResult",
    "Phase11Config",
    "Phase11Result",
    "build_phase11_dataset",
    "run_feature_intelligence",
]
