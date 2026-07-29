from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.execution.models import OrderRequest, OrderSnapshot, utc_now


class ExecutionDecision(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionPolicy:
    live_enabled: bool = False
    require_reconciliation: bool = True
    maximum_open_orders: int = 25
    maximum_order_notional: float = 25_000.0


@dataclass(frozen=True)
class ExecutionContext:
    market_price: float
    reconciliation_clear: bool = True
    safety_allows_trading: bool = True
    size_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.market_price <= 0:
            raise ValueError("market_price must be positive")
        if not 0.0 <= self.size_multiplier <= 1.0:
            raise ValueError("size_multiplier must be between zero and one")


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecutionDecision
    request: OrderRequest
    order_id: str = ""
    message: str = ""
    submitted_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class RecoveryReport:
    recovered_orders: tuple[OrderSnapshot, ...]
    active_order_ids: tuple[str, ...]
    duplicate_client_order_ids: tuple[str, ...]
