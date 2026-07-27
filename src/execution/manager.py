from __future__ import annotations

from src.execution.broker import Broker


class BrokerManager:
    def __init__(self) -> None:
        self._brokers: dict[str, Broker] = {}
        self._active: str | None = None

    def register(self, broker: Broker, *, make_active: bool = False) -> None:
        if broker.name in self._brokers:
            raise ValueError(f"broker already registered: {broker.name}")
        self._brokers[broker.name] = broker
        if make_active or self._active is None:
            self._active = broker.name

    def set_active(self, name: str) -> None:
        if name not in self._brokers:
            raise KeyError(name)
        self._active = name

    @property
    def active(self) -> Broker:
        if self._active is None:
            raise RuntimeError("no broker is registered")
        return self._brokers[self._active]

    def get(self, name: str) -> Broker:
        return self._brokers[name]
