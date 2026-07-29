from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.execution.models import AccountSnapshot, OrderSnapshot


class RobinhoodAssetClass(StrEnum):
    EQUITY = "equity"
    CRYPTO = "crypto"


class RobinhoodReleaseStage(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"
    SHADOW = "shadow"
    CANARY = "canary"
    LIVE = "live"
    HALTED = "halted"


class ReadinessLevel(StrEnum):
    BLOCKED = "blocked"
    NOT_READY = "not_ready"
    PAPER_READY = "paper_ready"
    CANARY_READY = "canary_ready"
    LIVE_READY = "live_ready"


@dataclass(frozen=True, slots=True)
class RobinhoodCredentialRefs:
    api_key_env: str = "ROBINHOOD_API_KEY"
    private_key_env: str = "ROBINHOOD_PRIVATE_KEY"

    def __post_init__(self) -> None:
        if not self.api_key_env.strip() or not self.private_key_env.strip():
            raise ValueError("credential environment variable names are required")


@dataclass(frozen=True, slots=True)
class RobinhoodLimits:
    max_order_notional: float = 1_000.0
    max_daily_notional: float = 5_000.0
    max_open_orders: int = 5
    max_symbol_exposure_fraction: float = 0.10
    canary_capital_fraction: float = 0.01

    def __post_init__(self) -> None:
        if self.max_order_notional <= 0 or self.max_daily_notional <= 0:
            raise ValueError("notional limits must be positive")
        if self.max_open_orders < 1:
            raise ValueError("max_open_orders must be positive")
        fractions = (self.max_symbol_exposure_fraction, self.canary_capital_fraction)
        if any(value <= 0 or value > 1 for value in fractions):
            raise ValueError("capital fractions must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class RobinhoodReadinessInputs:
    credentials_available: bool
    broker_connected: bool
    broker_healthy: bool
    reconciliation_clean: bool
    market_data_fresh: bool
    kill_switch_active: bool
    paper_days: int
    paper_orders: int
    paper_fill_ratio: float
    paper_rejection_rate: float
    max_drawdown: float
    unresolved_alerts: int = 0

    def __post_init__(self) -> None:
        if self.paper_days < 0 or self.paper_orders < 0 or self.unresolved_alerts < 0:
            raise ValueError("counts cannot be negative")
        if not 0 <= self.paper_fill_ratio <= 1:
            raise ValueError("paper_fill_ratio must be in [0, 1]")
        if not 0 <= self.paper_rejection_rate <= 1:
            raise ValueError("paper_rejection_rate must be in [0, 1]")
        if self.max_drawdown < 0:
            raise ValueError("max_drawdown cannot be negative")


@dataclass(frozen=True, slots=True)
class RobinhoodReadinessReport:
    level: ReadinessLevel
    score: float
    approved_stage: RobinhoodReleaseStage
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be in [0, 100]")


@dataclass(frozen=True, slots=True)
class RobinhoodOperationalSnapshot:
    generated_at: datetime
    stage: RobinhoodReleaseStage
    account: AccountSnapshot
    orders: tuple[OrderSnapshot, ...]
    daily_submitted_notional: float
    trading_allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.daily_submitted_notional < 0:
            raise ValueError("daily_submitted_notional cannot be negative")
