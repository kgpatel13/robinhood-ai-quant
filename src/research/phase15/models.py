from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase15Config:
    trades_path: Path = Path("reports/phase12_research_validation/simulated_trades.csv")
    output_root: Path = Path("reports/phase15_alpha_engine")
    random_seed: int = 42
    folds: int = 5
    minimum_train_rows: int = 500
    validation_fraction: float = 0.15
    test_fraction: float = 0.15
    probability_thresholds: tuple[float, ...] = (0.50, 0.525, 0.55, 0.575, 0.60, 0.625)
    minimum_test_trades: int = 50
    minimum_auc: float = 0.51
    minimum_profit_factor: float = 1.05
    maximum_drawdown: float = 0.35
    transaction_cost_bps: float = 10.0


@dataclass(frozen=True)
class Phase15Result:
    source_trades: int
    folds_completed: int
    models_trained: int
    champion_model: str
    selected_threshold: float
    diagnostics_passed: bool
    approved_for_phase16_review: bool
    approved_for_paper_trading: bool
    approved_for_live_trading: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
