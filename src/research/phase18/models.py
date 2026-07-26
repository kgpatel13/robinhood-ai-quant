from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase18Config:
    phase17_scores_path: Path = Path("reports/phase17_execution_intelligence/execution_scores.csv")
    phase17_equity_path: Path = Path(
        "reports/phase17_execution_intelligence/phase17_equity_curve.csv"
    )
    phase17_executed_path: Path = Path(
        "reports/phase17_execution_intelligence/phase17_executed_trades.csv"
    )
    output_root: Path = Path("reports/phase18_adaptive_optimizer")
    initial_capital: float = 10_000.0
    minimum_opportunity_score: float = 0.46
    minimum_model_win_rate: float = 0.48
    maximum_cost_to_edge_ratio: float = 0.35
    minimum_position_multiplier: float = 0.55
    maximum_position_multiplier: float = 1.35
    maximum_position_fraction: float = 0.15
    maximum_gross_exposure: float = 0.75
    maximum_asset_class_exposure: float = 0.50
    maximum_open_positions: int = 8
    portfolio_drawdown_limit: float = 0.20
    bootstrap_samples: int = 2000
    random_seed: int = 42
    minimum_sharpe_improvement: float = 0.01
    minimum_profit_factor_improvement: float = 0.0
    maximum_drawdown_deterioration: float = 0.005
    minimum_positive_fold_rate: float = 0.60
    minimum_bootstrap_probability: float = 0.60


@dataclass(frozen=True)
class Phase18Result:
    source_candidates: int
    optimized_candidates: int
    executed_trades: int
    rejected_trades: int
    diagnostics_passed: bool
    approved_for_phase19_review: bool
    approved_for_paper_trading: bool
    approved_for_live_trading: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
