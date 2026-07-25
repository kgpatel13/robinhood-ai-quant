from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FeatureIntelligenceConfig:
    dataset_path: Path = Path("data/ml_dataset/training_dataset.parquet")
    output_root: Path = Path("reports/phase11_feature_intelligence")
    target_column: str = "net_forward_return"
    classification_target: str = "positive_return_label"
    maximum_analysis_rows: int = 200_000
    correlation_threshold: float = 0.90
    near_constant_unique_fraction: float = 0.001
    outlier_z_threshold: float = 8.0
    drift_threshold: float = 0.35
    suspicious_target_correlation: float = 0.50
    minimum_stable_group_fraction: float = 0.60
    random_seed: int = 11

    def __post_init__(self) -> None:
        if self.maximum_analysis_rows < 1_000:
            raise ValueError("maximum_analysis_rows must be at least 1000")
        if not 0.0 < self.correlation_threshold < 1.0:
            raise ValueError("correlation_threshold must be between 0 and 1")
        if not 0.0 <= self.near_constant_unique_fraction < 1.0:
            raise ValueError("near_constant_unique_fraction must be in [0, 1)")
        if self.outlier_z_threshold <= 0.0:
            raise ValueError("outlier_z_threshold must be positive")
        if self.drift_threshold <= 0.0:
            raise ValueError("drift_threshold must be positive")
        if not 0.0 < self.suspicious_target_correlation < 1.0:
            raise ValueError("suspicious_target_correlation must be between 0 and 1")
        if not 0.0 <= self.minimum_stable_group_fraction <= 1.0:
            raise ValueError("minimum_stable_group_fraction must be in [0, 1]")


@dataclass(frozen=True)
class FeatureIntelligenceResult:
    rows_analyzed: int
    total_features: int
    recommended_keep: int
    recommended_review: int
    recommended_remove: int
    output: str
    diagnostics_passed: bool
    artifacts: dict[str, str] = field(default_factory=dict)
