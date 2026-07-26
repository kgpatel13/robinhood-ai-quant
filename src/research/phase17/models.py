from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase17Config:
    adaptive_allocations_path: Path = Path(
        "reports/phase16_portfolio_intelligence/adaptive_allocations.csv"
    )
    phase16_equity_path: Path = Path(
        "reports/phase16_portfolio_intelligence/phase16_equity_curve.csv"
    )
    phase16_executed_path: Path = Path(
        "reports/phase16_portfolio_intelligence/phase16_executed_trades.csv"
    )
    output_root: Path = Path("reports/phase17_execution_intelligence")
    initial_capital: float = 10_000.0
    base_cost_bps: float = 10.0
    maximum_incremental_slippage_bps: float = 45.0
    stock_liquidity_floor: float = 0.55
    crypto_liquidity_floor: float = 0.40
    minimum_execution_score: float = 0.42
    maximum_position_fraction: float = 0.15
    maximum_gross_exposure: float = 0.75
    maximum_asset_class_exposure: float = 0.50
    maximum_open_positions: int = 8
    portfolio_drawdown_limit: float = 0.20
    bootstrap_samples: int = 2000
    random_seed: int = 42
    minimum_sharpe_improvement: float = 0.01
    minimum_profit_factor_improvement: float = 0.0
    maximum_drawdown_deterioration: float = 0.01
    minimum_positive_fold_rate: float = 0.60
    minimum_bootstrap_probability: float = 0.60


@dataclass(frozen=True)
class Phase17Result:
    source_candidates: int
    execution_candidates: int
    executed_trades: int
    rejected_trades: int
    diagnostics_passed: bool
    approved_for_phase18_review: bool
    approved_for_paper_trading: bool
    approved_for_live_trading: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
