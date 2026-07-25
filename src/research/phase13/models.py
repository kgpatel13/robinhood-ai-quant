from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase13Config:
    trades_path: Path = Path("reports/phase12_research_validation/simulated_trades.csv")
    output_root: Path = Path("reports/phase13_portfolio_engine")
    initial_capital: float = 10_000.0
    target_risk_per_trade: float = 0.005
    maximum_position_fraction: float = 0.15
    maximum_gross_exposure: float = 0.75
    maximum_asset_class_exposure: float = 0.50
    maximum_open_positions: int = 8
    confidence_floor: float = 0.50
    confidence_ceiling: float = 0.75
    volatility_floor: float = 0.005
    volatility_ceiling: float = 0.08
    daily_loss_limit: float = 0.03
    portfolio_drawdown_limit: float = 0.20
    recovery_drawdown: float = 0.10
    drawdown_cooldown_days: int = 30
    reset_risk_peak_after_cooldown: bool = True
    slippage_bps: float = 5.0
    commission_bps: float = 0.0
    minimum_trades: int = 50
    maximum_allowed_drawdown: float = 0.30

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        for name in (
            "target_risk_per_trade",
            "maximum_position_fraction",
            "maximum_gross_exposure",
            "maximum_asset_class_exposure",
            "daily_loss_limit",
            "portfolio_drawdown_limit",
            "recovery_drawdown",
            "maximum_allowed_drawdown",
        ):
            value = float(getattr(self, name))
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.recovery_drawdown >= self.portfolio_drawdown_limit:
            raise ValueError("recovery_drawdown must be below portfolio_drawdown_limit")
        if self.drawdown_cooldown_days < 1:
            raise ValueError("drawdown_cooldown_days must be positive")
        if self.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be positive")
        if not 0.0 <= self.confidence_floor < self.confidence_ceiling <= 1.0:
            raise ValueError("confidence bounds are invalid")
        if not 0.0 < self.volatility_floor < self.volatility_ceiling:
            raise ValueError("volatility bounds are invalid")
        if min(self.slippage_bps, self.commission_bps) < 0.0:
            raise ValueError("cost assumptions cannot be negative")


@dataclass(frozen=True)
class Phase13Result:
    source_trades: int
    executed_trades: int
    rejected_trades: int
    diagnostics_passed: bool
    approved_for_phase14_review: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
