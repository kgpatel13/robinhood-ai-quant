from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ModelIntelligenceConfig:
    dataset_path: Path = Path("data/ml_dataset/training_dataset.parquet")
    label_signoff_path: Path = Path("reports/phase11_label_intelligence/phase11_label_signoff.json")
    output_root: Path = Path("reports/phase11_model_intelligence")
    maximum_rows_per_horizon: int = 120_000
    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    purge_bars: int = 20
    embargo_bars: int = 5
    random_seed: int = 12
    minimum_train_rows: int = 2_000
    probability_thresholds: tuple[float, ...] = (
        0.45,
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
    )
    minimum_test_auc: float = 0.50
    minimum_test_brier_improvement: float = 0.0
    minimum_test_trades: int = 100
    maximum_test_drawdown: float = 0.50

    def __post_init__(self) -> None:
        if self.maximum_rows_per_horizon < 1_000:
            raise ValueError("maximum_rows_per_horizon must be at least 1000")
        if not 0.0 < self.train_fraction < 1.0:
            raise ValueError("train_fraction must be in (0, 1)")
        if not 0.0 < self.validation_fraction < 1.0:
            raise ValueError("validation_fraction must be in (0, 1)")
        if self.train_fraction + self.validation_fraction >= 1.0:
            raise ValueError("train and validation fractions must leave a test partition")
        if min(self.purge_bars, self.embargo_bars) < 0:
            raise ValueError("purge_bars and embargo_bars cannot be negative")
        if self.minimum_train_rows < 100:
            raise ValueError("minimum_train_rows must be at least 100")
        if not self.probability_thresholds:
            raise ValueError("probability_thresholds cannot be empty")
        if any(not 0.0 < value < 1.0 for value in self.probability_thresholds):
            raise ValueError("probability thresholds must be in (0, 1)")
        if not 0.0 <= self.minimum_test_auc <= 1.0:
            raise ValueError("minimum_test_auc must be in [0, 1]")
        if self.minimum_test_trades < 1:
            raise ValueError("minimum_test_trades must be positive")
        if not 0.0 <= self.maximum_test_drawdown <= 1.0:
            raise ValueError("maximum_test_drawdown must be in [0, 1]")


@dataclass(frozen=True)
class ModelIntelligenceResult:
    rows_analyzed: int
    horizons_analyzed: int
    models_trained: int
    champions_selected: int
    diagnostics_passed: bool
    approved_for_phase12_review: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
