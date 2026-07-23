from __future__ import annotations

from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from time import perf_counter
from types import TracebackType


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._timings: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: float = 1.0) -> None:
        self._counters[name] += value

    def observe(self, name: str, seconds: float) -> None:
        self._timings[name].append(seconds)

    def snapshot(self) -> dict[str, object]:
        return {
            "counters": dict(sorted(self._counters.items())),
            "timings": {
                name: {
                    "count": len(values),
                    "total_seconds": sum(values),
                    "average_seconds": sum(values) / len(values),
                }
                for name, values in sorted(self._timings.items())
                if values
            },
        }


@dataclass
class Timer(AbstractContextManager["Timer"]):
    collector: MetricsCollector
    name: str
    _started: float = 0.0

    def __enter__(self) -> Timer:
        self._started = perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.collector.observe(self.name, perf_counter() - self._started)
