from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

E = TypeVar("E", bound="Event")
EventHandler = Callable[[Any], None]


@dataclass(frozen=True)
class Event:
    run_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class MarketDataLoaded(Event):
    symbols: tuple[str, ...] = ()
    rows: int = 0


@dataclass(frozen=True)
class BacktestCompleted(Event):
    strategy: str = ""
    final_equity: float = 0.0


@dataclass(frozen=True)
class ReportGenerated(Event):
    report_type: str = ""
    path: str = ""


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        handlers = self._handlers[event_type]
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: Event) -> int:
        delivered = 0
        for event_type, handlers in tuple(self._handlers.items()):
            if isinstance(event, event_type):
                for handler in tuple(handlers):
                    handler(event)
                    delivered += 1
        return delivered

    def subscriber_count(self, event_type: type[Event] | None = None) -> int:
        if event_type is not None:
            return len(self._handlers.get(event_type, []))
        return sum(len(handlers) for handlers in self._handlers.values())
