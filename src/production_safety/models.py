from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SafetyState(StrEnum):
    ARMED = "armed"
    THROTTLED = "throttled"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class SafetyTelemetry:
    timestamp: datetime
    daily_pnl: float
    peak_equity: float
    current_equity: float
    consecutive_losses: int
    order_rejection_rate: float
    data_age_seconds: float
    broker_connected: bool
    manual_kill_switch: bool = False

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.peak_equity <= 0 or self.current_equity <= 0:
            raise ValueError("equity values must be positive")
        if self.current_equity > self.peak_equity:
            raise ValueError("current_equity cannot exceed peak_equity")
        if self.consecutive_losses < 0 or self.data_age_seconds < 0:
            raise ValueError("counts and age cannot be negative")
        if not 0.0 <= self.order_rejection_rate <= 1.0:
            raise ValueError("order_rejection_rate must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class SafetyPolicy:
    maximum_daily_loss: float = 1_000.0
    maximum_drawdown: float = 0.08
    maximum_consecutive_losses: int = 5
    maximum_order_rejection_rate: float = 0.25
    maximum_data_age_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    state: SafetyState
    size_multiplier: float
    allow_new_orders: bool
    reasons: tuple[str, ...]
