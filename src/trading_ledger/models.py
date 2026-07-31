from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class LedgerEventType(StrEnum):
    ORDER = "order"
    FILL = "fill"
    ACCOUNT_SNAPSHOT = "account_snapshot"
    RISK = "risk"


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    starting_cash: float
    cash: float
    market_value: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    order_count: int
    fill_count: int
    as_of: datetime


@dataclass(frozen=True, slots=True)
class LedgerPosition:
    symbol: str
    quantity: float
    average_cost: float
    market_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.market_price - self.average_cost)


def utc_now() -> datetime:
    return datetime.now(UTC)
