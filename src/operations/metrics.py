from __future__ import annotations

from collections import defaultdict


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, amount: float = 1.0) -> None:
        self._counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {"counters": dict(self._counters), "gauges": dict(self._gauges)}
