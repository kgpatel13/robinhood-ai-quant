from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ComponentState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class PlatformState(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    state: ComponentState
    message: str = ""
    observed_at: datetime | None = None
    latency_ms: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("component name cannot be empty")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TradingMetrics:
    equity: float
    daily_pnl: float
    gross_exposure: float
    net_exposure: float
    open_positions: int
    open_orders: int
    fill_ratio: float
    rejection_rate: float

    def __post_init__(self) -> None:
        if self.equity < 0 or self.gross_exposure < 0:
            raise ValueError("equity and gross exposure cannot be negative")
        if self.open_positions < 0 or self.open_orders < 0:
            raise ValueError("counts cannot be negative")
        if not 0.0 <= self.fill_ratio <= 1.0:
            raise ValueError("fill_ratio must be in [0, 1]")
        if not 0.0 <= self.rejection_rate <= 1.0:
            raise ValueError("rejection_rate must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ModelHealthSummary:
    active_models: int = 0
    drifting_models: int = 0
    retraining_recommended: int = 0

    def __post_init__(self) -> None:
        values = (self.active_models, self.drifting_models, self.retraining_recommended)
        if any(value < 0 for value in values):
            raise ValueError("model counts cannot be negative")


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    generated_at: datetime
    platform_state: PlatformState
    trading_allowed: bool
    metrics: TradingMetrics
    components: tuple[ComponentHealth, ...] = field(default_factory=tuple)
    model_health: ModelHealthSummary = field(default_factory=ModelHealthSummary)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
