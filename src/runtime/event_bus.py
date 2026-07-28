from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import count
from threading import RLock

from src.runtime.events import EventType, RuntimeEvent

EventHandler = Callable[[RuntimeEvent], None]


@dataclass(order=True)
class _QueuedEvent:
    priority: int
    sequence: int
    event: RuntimeEvent = field(compare=False)


class EventBus:
    """Thread-safe, deterministic in-process event bus."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._all_handlers: list[EventHandler] = []
        self._queue: list[_QueuedEvent] = []
        self._counter = count()
        self._lock = RLock()
        self._dead_letters: list[tuple[RuntimeEvent, str]] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        with self._lock:
            self._all_handlers.append(handler)

    def publish(self, event: RuntimeEvent) -> None:
        with self._lock:
            heapq.heappush(
                self._queue,
                _QueuedEvent(int(event.priority), next(self._counter), event),
            )

    def drain(self, *, max_events: int | None = None) -> int:
        processed = 0
        while max_events is None or processed < max_events:
            with self._lock:
                if not self._queue:
                    break
                event = heapq.heappop(self._queue).event
                handlers = [*self._handlers[event.event_type], *self._all_handlers]
            for handler in handlers:
                try:
                    handler(event)
                except Exception as exc:  # defensive runtime boundary
                    with self._lock:
                        self._dead_letters.append((event, str(exc)))
            processed += 1
        return processed

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def dead_letters(self) -> tuple[tuple[RuntimeEvent, str], ...]:
        with self._lock:
            return tuple(self._dead_letters)
