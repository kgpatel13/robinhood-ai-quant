from __future__ import annotations

from src.brokers.base import BrokerAdapter


class BrokerRegistry:
    """Named adapter registry used by execution and operations layers."""

    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {}

    def register(self, adapter: BrokerAdapter, *, replace: bool = False) -> None:
        key = adapter.name.strip().lower()
        if not key:
            raise ValueError("broker adapter name is required")
        if key in self._adapters and not replace:
            raise ValueError(f"broker adapter is already registered: {key}")
        self._adapters[key] = adapter

    def get(self, name: str) -> BrokerAdapter:
        key = name.strip().lower()
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"broker adapter is not registered: {key}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
