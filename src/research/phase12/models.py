from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase12Config:
    dataset_path: Path = Path("data/ml_dataset/training_dataset.parquet")
    phase11_champions_path: Path = Path("reports/phase11_model_intelligence/champion_models.csv")
    output_root: Path = Path("reports/phase12_research_validation")
    horizons: tuple[int, ...] = (20, 10)
    maximum_rows_per_horizon: int = 160_000
    folds: int = 4
    minimum_train_timestamps: int = 300
    calibration_fraction: float = 0.15
    test_fraction: float = 0.15
    purge_bars: int = 20
    embargo_bars: int = 5
    random_seed: int = 12
    probability_thresholds: tuple[float, ...] = (0.50, 0.55, 0.60, 0.65, 0.70)
    maximum_open_positions: int = 5
    initial_capital: float = 10_000.0
    allocation_per_trade: float = 0.20
    slippage_bps: float = 5.0
    commission_bps: float = 0.0
    minimum_fold_auc: float = 0.51
    minimum_median_auc: float = 0.52
    minimum_profitable_folds: float = 0.60
    minimum_total_trades: int = 100
    maximum_drawdown: float = 0.30

    def __post_init__(self) -> None:
        if self.maximum_rows_per_horizon < 1_000:
            raise ValueError("maximum_rows_per_horizon must be at least 1000")
        if self.folds < 2:
            raise ValueError("folds must be at least 2")
        if self.minimum_train_timestamps < 20:
            raise ValueError("minimum_train_timestamps must be at least 20")
        if not 0.05 <= self.calibration_fraction <= 0.30:
            raise ValueError("calibration_fraction must be between 0.05 and 0.30")
        if not 0.05 <= self.test_fraction <= 0.30:
            raise ValueError("test_fraction must be between 0.05 and 0.30")
        if min(self.purge_bars, self.embargo_bars) < 0:
            raise ValueError("purge_bars and embargo_bars cannot be negative")
        if not self.horizons:
            raise ValueError("horizons cannot be empty")
        if any(value <= 0 for value in self.horizons):
            raise ValueError("horizons must be positive")
        if any(not 0.0 < value < 1.0 for value in self.probability_thresholds):
            raise ValueError("probability thresholds must be in (0, 1)")
        if self.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be positive")
        if self.initial_capital <= 0.0:
            raise ValueError("initial_capital must be positive")
        if not 0.0 < self.allocation_per_trade <= 1.0:
            raise ValueError("allocation_per_trade must be in (0, 1]")
        if min(self.slippage_bps, self.commission_bps) < 0.0:
            raise ValueError("cost assumptions cannot be negative")
        if self.minimum_total_trades < 1:
            raise ValueError("minimum_total_trades must be positive")
        if not 0.0 <= self.maximum_drawdown <= 1.0:
            raise ValueError("maximum_drawdown must be in [0, 1]")


@dataclass(frozen=True)
class Phase12Result:
    rows_analyzed: int
    horizons_analyzed: int
    folds_completed: int
    models_trained: int
    diagnostics_passed: bool
    approved_for_paper_trading_review: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
