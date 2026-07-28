from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class PaperOrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class PaperOrderStatus(StrEnum):
    NEW = "new"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    source: str

    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class PaperOrderRequest:
    order_id: str
    symbol: str
    side: PaperOrderSide
    quantity: int
    submitted_at: datetime
    strategy: str
    limit_price: float | None = None


@dataclass(frozen=True)
class PaperFill:
    order_id: str
    symbol: str
    side: PaperOrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float
    slippage_bps: float


@dataclass(frozen=True)
class PaperOrderResult:
    request: PaperOrderRequest
    status: PaperOrderStatus
    reason: str
    fill: PaperFill | None = None


@dataclass
class PaperPosition:
    symbol: str
    quantity: int
    average_price: float
    strategy: str
    opened_at: datetime
    last_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.last_price - self.average_price)


@dataclass
class PaperAccount:
    starting_cash: float
    cash: float
    realized_pnl: float = 0.0
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    orders: list[PaperOrderResult] = field(default_factory=list)

    @property
    def market_value(self) -> float:
        return sum(position.market_value for position in self.positions.values())

    @property
    def equity(self) -> float:
        return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> float:
        return sum(position.unrealized_pnl for position in self.positions.values())
