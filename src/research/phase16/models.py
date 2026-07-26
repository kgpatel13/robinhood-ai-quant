from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase16Config:
    selected_trades_path: Path = Path("reports/phase15_alpha_engine/selected_trades.csv")
    phase15_equity_path: Path = Path("reports/phase15_alpha_engine/portfolio_equity_curve.csv")
    phase15_executed_path: Path = Path("reports/phase15_alpha_engine/portfolio_executed_trades.csv")
    output_root: Path = Path("reports/phase16_portfolio_intelligence")
    initial_capital: float = 10_000.0
    target_risk_per_trade: float = 0.005
    target_portfolio_volatility: float = 0.12
    maximum_position_fraction: float = 0.15
    minimum_position_fraction: float = 0.01
    maximum_gross_exposure: float = 0.75
    maximum_asset_class_exposure: float = 0.50
    maximum_open_positions: int = 8
    fractional_kelly: float = 0.25
    maximum_kelly_fraction: float = 0.12
    correlation_soft_limit: float = 0.60
    correlation_hard_limit: float = 0.85
    drawdown_soft_limit: float = 0.10
    drawdown_hard_limit: float = 0.20
    minimum_model_observations: int = 30
    model_lookback_trades: int = 100
    bootstrap_samples: int = 2000
    random_seed: int = 42
    minimum_sharpe_improvement: float = 0.02
    minimum_profit_factor_improvement: float = 0.0
    maximum_drawdown_deterioration: float = 0.01
    minimum_positive_fold_rate: float = 0.60


@dataclass(frozen=True)
class Phase16Result:
    source_trades: int
    executed_trades: int
    rejected_trades: int
    diagnostics_passed: bool
    approved_for_phase17_review: bool
    approved_for_paper_trading: bool
    approved_for_live_trading: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
