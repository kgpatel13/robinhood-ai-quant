from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase14Config:
    executed_trades_path: Path = Path("reports/phase13_portfolio_engine/executed_trades.csv")
    rejected_signals_path: Path = Path("reports/phase13_portfolio_engine/rejected_signals.csv")
    equity_curve_path: Path = Path("reports/phase13_portfolio_engine/portfolio_equity_curve.csv")
    output_root: Path = Path("reports/phase14_research_intelligence")
    risk_free_rate: float = 0.0
    minimum_trades_per_group: int = 10
    annual_periods: int = 365
    regime_window: int = 50
    minimum_total_trades: int = 50
    maximum_allowed_drawdown: float = 0.30


@dataclass(frozen=True)
class Phase14Result:
    executed_trades: int
    start_date: str
    end_date: str
    calendar_years: float
    diagnostics_passed: bool
    approved_for_phase15_review: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
