from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.execution.models import OrderReceipt, OrderRequest
from src.multi_agent_ai.models import CoordinatedDecision
from src.production_platform.models import ProductionSnapshot


class OperationalMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    SHADOW = "shadow"
    CANARY = "canary"
    LIVE = "live"
    HALTED = "halted"


class CycleStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MarketObservation:
    symbol: str
    price: float
    observed_at: datetime
    features: Mapping[str, float] = field(default_factory=dict)
    stale_after_seconds: int = 120

    def __post_init__(self) -> None:
        if not self.symbol.strip() or self.price <= 0:
            raise ValueError("symbol and positive price are required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")


@dataclass(frozen=True, slots=True)
class CycleRequest:
    cycle_id: str
    mode: OperationalMode
    observation: MarketObservation
    requested_notional: float
    strategy_id: str
    reconciliation_clear: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cycle_id.strip() or not self.strategy_id.strip():
            raise ValueError("cycle_id and strategy_id are required")
        if self.requested_notional <= 0:
            raise ValueError("requested_notional must be positive")


@dataclass(frozen=True, slots=True)
class TranslationPolicy:
    minimum_notional: float = 1.0
    maximum_notional: float = 100_000.0
    allow_fractional: bool = True
    allow_short: bool = False

    def __post_init__(self) -> None:
        if self.minimum_notional <= 0 or self.maximum_notional < self.minimum_notional:
            raise ValueError("invalid notional bounds")


@dataclass(frozen=True, slots=True)
class CycleResult:
    cycle_id: str
    symbol: str
    mode: OperationalMode
    status: CycleStatus
    decision: CoordinatedDecision | None
    production: ProductionSnapshot | None
    order_request: OrderRequest | None
    order_receipt: OrderReceipt | None
    reasons: tuple[str, ...]
    audit_record: Mapping[str, object]
