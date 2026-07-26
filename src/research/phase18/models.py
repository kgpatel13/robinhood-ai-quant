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
    output_root: Path = Path("reports/phase18_6_institutional_validation")
    initial_capital: float = 10_000.0
    soft_confidence_weight: float = 0.50
    soft_execution_weight: float = 0.25
    soft_model_health_weight: float = 0.15
    soft_diversification_weight: float = 0.10
    probability_anchor_weight: float = 0.55
    sizing_strength: float = 0.10
    minimum_volatility_multiplier: float = 0.80
    maximum_volatility_multiplier: float = 1.20
    minimum_capital_utilization_ratio: float = 0.95
    maximum_position_fraction: float = 0.15
    maximum_gross_exposure: float = 0.75
    maximum_asset_class_exposure: float = 0.50
    maximum_open_positions: int = 8
    portfolio_drawdown_limit: float = 0.20
    bootstrap_samples: int = 5000
    bootstrap_block_size: int = 10
    monte_carlo_samples: int = 5000
    maximum_cost_shock_bps: float = 5.0
    random_seed: int = 42
    minimum_sharpe_improvement: float = 0.01
    minimum_profit_factor_improvement: float = 0.0
    maximum_drawdown_deterioration: float = 0.005
    minimum_positive_fold_rate: float = 0.60
    minimum_block_bootstrap_probability: float = 0.60
    minimum_monte_carlo_profitable_probability: float = 0.95
    performance_score_weight: float = 0.40
    statistical_score_weight: float = 0.30
    robustness_score_weight: float = 0.20
    engineering_score_weight: float = 0.10
    minimum_composite_score: float = 0.80


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
