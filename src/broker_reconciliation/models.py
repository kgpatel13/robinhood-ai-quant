from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReconciliationDecision(StrEnum):
    MATCHED = "matched"
    WARNING = "warning"
    HALT = "halt"


class DiscrepancyType(StrEnum):
    CASH = "cash"
    POSITION_MISSING_LOCAL = "position_missing_local"
    POSITION_MISSING_BROKER = "position_missing_broker"
    POSITION_QUANTITY = "position_quantity"
    ORDER_MISSING_LOCAL = "order_missing_local"
    ORDER_MISSING_BROKER = "order_missing_broker"
    ORDER_STATUS = "order_status"
    DUPLICATE_CLIENT_ORDER_ID = "duplicate_client_order_id"


@dataclass(frozen=True)
class ReconciliationDiscrepancy:
    discrepancy_type: DiscrepancyType
    entity_id: str
    message: str
    severity: int = 1


@dataclass(frozen=True)
class ReconciliationPolicy:
    cash_tolerance: float = 1.0
    quantity_tolerance: float = 1e-6
    warning_score: int = 1
    halt_score: int = 3

    def __post_init__(self) -> None:
        if self.cash_tolerance < 0 or self.quantity_tolerance < 0:
            raise ValueError("reconciliation tolerances cannot be negative")
        if self.warning_score < 1 or self.halt_score < self.warning_score:
            raise ValueError("invalid reconciliation score thresholds")


@dataclass(frozen=True)
class ReconciliationReport:
    decision: ReconciliationDecision
    score: int
    discrepancies: tuple[ReconciliationDiscrepancy, ...]

    @property
    def trading_allowed(self) -> bool:
        return self.decision is not ReconciliationDecision.HALT
