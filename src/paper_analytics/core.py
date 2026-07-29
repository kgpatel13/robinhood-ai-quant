from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import numpy as np


class PaperEventType(StrEnum):
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    REJECTION = "rejection"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class PaperTradeEvent:
    trade_id: str
    event_type: PaperEventType
    timestamp: datetime
    symbol: str
    strategy: str
    quantity: float = 0.0
    price: float | None = None
    expected_price: float | None = None
    pnl: float | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PaperAnalyticsReport:
    signals: int
    orders: int
    fills: int
    rejections: int
    closed_trades: int
    fill_ratio: float
    win_rate: float
    expectancy: float
    profit_factor: float
    total_pnl: float
    average_slippage_bps: float
    maximum_drawdown: float


class PaperAnalyticsTracker:
    """In-memory lifecycle analytics for paper trades; does not submit orders."""

    def __init__(self) -> None:
        self._events: list[PaperTradeEvent] = []

    def record(self, event: PaperTradeEvent) -> None:
        if event.timestamp.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware")
        if event.quantity < 0:
            raise ValueError("quantity cannot be negative")
        self._events.append(event)

    def events(self) -> tuple[PaperTradeEvent, ...]:
        return tuple(sorted(self._events, key=lambda item: item.timestamp))

    def report(self, *, strategy: str | None = None) -> PaperAnalyticsReport:
        events = [event for event in self._events if strategy is None or event.strategy == strategy]
        signals = sum(event.event_type is PaperEventType.SIGNAL for event in events)
        orders = sum(event.event_type is PaperEventType.ORDER for event in events)
        fills = [event for event in events if event.event_type is PaperEventType.FILL]
        rejections = sum(event.event_type is PaperEventType.REJECTION for event in events)
        closes = [
            event
            for event in events
            if event.event_type is PaperEventType.CLOSE and event.pnl is not None
        ]
        pnls = np.asarray([event.pnl for event in closes if event.pnl is not None], dtype=float)
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        slippages = [
            abs(event.price - event.expected_price) / event.expected_price * 10_000.0
            for event in fills
            if event.price is not None
            and event.expected_price is not None
            and event.expected_price > 0
        ]
        total = float(pnls.sum()) if len(pnls) else 0.0
        equity = np.cumsum(pnls) if len(pnls) else np.asarray([], dtype=float)
        peaks = np.maximum.accumulate(np.concatenate(([0.0], equity)))
        path = np.concatenate(([0.0], equity))
        drawdown = float(np.max(peaks - path)) if len(path) else 0.0
        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = abs(float(losses.sum())) if len(losses) else 0.0
        return PaperAnalyticsReport(
            signals=signals,
            orders=orders,
            fills=len(fills),
            rejections=rejections,
            closed_trades=len(closes),
            fill_ratio=len(fills) / orders if orders else 0.0,
            win_rate=len(wins) / len(pnls) if len(pnls) else 0.0,
            expectancy=float(pnls.mean()) if len(pnls) else 0.0,
            profit_factor=gross_profit / gross_loss
            if gross_loss
            else (float("inf") if gross_profit else 0.0),
            total_pnl=total,
            average_slippage_bps=float(np.mean(slippages)) if slippages else 0.0,
            maximum_drawdown=drawdown,
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
