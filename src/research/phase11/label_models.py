from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LabelIntelligenceConfig:
    dataset_path: Path = Path("data/ml_dataset/training_dataset.parquet")
    output_root: Path = Path("reports/phase11_label_intelligence")
    maximum_analysis_rows: int = 300_000
    minimum_horizon_rows: int = 5_000
    minimum_positive_rate: float = 0.20
    maximum_positive_rate: float = 0.80
    maximum_extreme_return_fraction: float = 0.02
    extreme_return_threshold: float = 0.25
    minimum_quality_index: float = 0.55
    random_seed: int = 12

    def __post_init__(self) -> None:
        if self.maximum_analysis_rows < 1_000:
            raise ValueError("maximum_analysis_rows must be at least 1000")
        if self.minimum_horizon_rows < 100:
            raise ValueError("minimum_horizon_rows must be at least 100")
        if not 0.0 <= self.minimum_positive_rate < self.maximum_positive_rate <= 1.0:
            raise ValueError("positive-rate limits are invalid")
        if not 0.0 <= self.maximum_extreme_return_fraction <= 1.0:
            raise ValueError("maximum_extreme_return_fraction must be in [0, 1]")
        if self.extreme_return_threshold <= 0.0:
            raise ValueError("extreme_return_threshold must be positive")
        if not 0.0 <= self.minimum_quality_index <= 1.0:
            raise ValueError("minimum_quality_index must be in [0, 1]")


@dataclass(frozen=True)
class LabelIntelligenceResult:
    rows_analyzed: int
    horizons_analyzed: int
    approved_horizons: int
    review_horizons: int
    output: str
    diagnostics_passed: bool
    artifacts: dict[str, str] = field(default_factory=dict)
