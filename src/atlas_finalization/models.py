from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ValidationDecision(StrEnum):
    REJECT = "reject"
    WATCH = "watch"
    PROMOTE = "promote"


class OperationStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    annualized_return: float
    sharpe_ratio: float
    maximum_drawdown: float
    trade_count: int
    out_of_sample_return: float
    cost_adjusted_return: float
    parameter_stability: float
    regime_coverage: float

    def __post_init__(self) -> None:
        if self.trade_count < 0:
            raise ValueError("trade_count cannot be negative")
        if self.maximum_drawdown < 0:
            raise ValueError("maximum_drawdown cannot be negative")
        for value in (self.parameter_stability, self.regime_coverage):
            if not 0 <= value <= 1:
                raise ValueError("stability and coverage values must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ValidationScorecard:
    strategy_id: str
    score: float
    decision: ValidationDecision
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id is required")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be in [0, 100]")


@dataclass(frozen=True, slots=True)
class PaperSessionMetrics:
    trading_days: int
    submitted_orders: int
    filled_orders: int
    rejected_orders: int
    realized_pnl: float
    maximum_drawdown: float
    duplicate_orders: int = 0
    reconciliation_failures: int = 0

    def __post_init__(self) -> None:
        counts = (
            self.trading_days,
            self.submitted_orders,
            self.filled_orders,
            self.rejected_orders,
            self.duplicate_orders,
            self.reconciliation_failures,
        )
        if any(value < 0 for value in counts):
            raise ValueError("paper-session counts cannot be negative")
        if self.maximum_drawdown < 0:
            raise ValueError("maximum_drawdown cannot be negative")
        if self.filled_orders + self.rejected_orders > self.submitted_orders:
            raise ValueError("filled and rejected orders cannot exceed submitted orders")

    @property
    def fill_ratio(self) -> float:
        return self.filled_orders / self.submitted_orders if self.submitted_orders else 0.0

    @property
    def rejection_rate(self) -> float:
        return self.rejected_orders / self.submitted_orders if self.submitted_orders else 0.0


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    generated_at: datetime
    market_data_fresh: bool
    broker_connected: bool
    reconciliation_clean: bool
    kill_switch_active: bool
    error_rate: float
    decision_latency_ms: float
    broker_latency_ms: float
    unresolved_alerts: int = 0

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not 0 <= self.error_rate <= 1:
            raise ValueError("error_rate must be in [0, 1]")
        if self.decision_latency_ms < 0 or self.broker_latency_ms < 0:
            raise ValueError("latency values cannot be negative")
        if self.unresolved_alerts < 0:
            raise ValueError("unresolved_alerts cannot be negative")


@dataclass(frozen=True, slots=True)
class OperationalAssessment:
    status: OperationStatus
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be in [0, 100]")


@dataclass(frozen=True, slots=True)
class TradeAttributionInput:
    trade_id: str
    gross_pnl: float
    fees: float
    slippage: float
    strategy_weight: float
    agent_weight: float
    sizing_weight: float

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id is required")
        if self.fees < 0 or self.slippage < 0:
            raise ValueError("fees and slippage cannot be negative")


@dataclass(frozen=True, slots=True)
class TradeAttribution:
    trade_id: str
    net_pnl: float
    strategy_contribution: float
    agent_contribution: float
    sizing_contribution: float
    cost_drag: float


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    experiment_id: str
    strategy_id: str
    strategy_version: str
    code_version: str
    dataset_id: str
    parameters: dict[str, int | float | str | bool]
    metrics: ValidationMetrics
    created_at: datetime
    notes: str = ""

    def __post_init__(self) -> None:
        required = (
            self.experiment_id,
            self.strategy_id,
            self.strategy_version,
            self.code_version,
            self.dataset_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment identity fields are required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
