from src.research.benchmark import buy_and_hold_curve, compare_to_benchmark
from src.research.engine import OptimizationEngine
from src.research.models import (
    OptimizationConfig,
    OptimizationResult,
    OptimizationTrial,
    ParameterSpec,
)
from src.research.phase5 import run_phase5_bundle
from src.research.report import write_optimization_report
from src.research.scorecard import Scorecard, build_scorecard
from src.research.stability import parameter_stability
from src.research.validation import (
    DatasetValidation,
    discover_datasets,
    validate_dataset,
)
from src.research.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
)

__all__ = [
    "DatasetValidation",
    "OptimizationConfig",
    "OptimizationEngine",
    "OptimizationResult",
    "OptimizationTrial",
    "ParameterSpec",
    "Scorecard",
    "WalkForwardConfig",
    "WalkForwardEngine",
    "WalkForwardResult",
    "build_scorecard",
    "buy_and_hold_curve",
    "compare_to_benchmark",
    "discover_datasets",
    "parameter_stability",
    "run_phase5_bundle",
    "validate_dataset",
    "write_optimization_report",
]
