from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase15Config:
    trades_path: Path = Path("reports/phase12_research_validation/simulated_trades.csv")
    output_root: Path = Path("reports/phase15_alpha_engine")
    stock_benchmark_path: Path | None = Path("data/benchmarks/SPY.csv")
    crypto_benchmark_path: Path | None = Path("data/benchmarks/BTC-USD.csv")
    random_seed: int = 42
    folds: int = 5
    minimum_train_rows: int = 500
    validation_fraction: float = 0.15
    test_fraction: float = 0.15
    probability_thresholds: tuple[float, ...] = (0.50, 0.525, 0.55, 0.575, 0.60, 0.625)
    ev_thresholds: tuple[float, ...] = (0.0, 0.001, 0.0025, 0.005, 0.01)
    minimum_test_trades: int = 50
    minimum_auc: float = 0.50
    minimum_profit_factor: float = 1.15
    maximum_drawdown: float = 0.30
    transaction_cost_bps: float = 10.0
    minimum_positive_folds: int = 4
    maximum_pnl_concentration: float = 0.40
    minimum_sharpe_improvement: float = 0.0
    minimum_sortino_improvement: float = 0.0
    bootstrap_samples: int = 2000


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
