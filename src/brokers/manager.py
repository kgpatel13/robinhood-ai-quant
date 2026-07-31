from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from src.brokers.base import BrokerAdapter
from src.brokers.models import BrokerHealth
from src.brokers.registry import BrokerRegistry
from src.execution.models import OrderReceipt, OrderRequest


class AssetClass(StrEnum):
    EQUITY = "equity"
    CRYPTO = "crypto"


@dataclass(frozen=True, slots=True)
class BrokerRoute:
    asset_class: AssetClass
    broker_name: str


@dataclass(frozen=True, slots=True)
class ManagedBrokerHealth:
    broker_name: str
    health: BrokerHealth


class UnifiedBrokerManager:
    """Single broker-selection boundary for strategies and execution workflows.

    Routing is explicit and fail-closed. Registering an adapter does not grant live
    execution permission; each adapter's own safety policy still applies.
    """

    def __init__(
        self,
        registry: BrokerRegistry | None = None,
        *,
        routes: Sequence[BrokerRoute] = (),
    ) -> None:
        self._registry = registry or BrokerRegistry()
        self._routes: dict[AssetClass, str] = {}
        for route in routes:
            self.set_route(route.asset_class, route.broker_name)

    @property
    def registry(self) -> BrokerRegistry:
        return self._registry

    def register(self, adapter: BrokerAdapter, *, replace: bool = False) -> None:
        self._registry.register(adapter, replace=replace)

    def set_route(self, asset_class: AssetClass, broker_name: str) -> None:
        normalized = broker_name.strip().lower()
        if not normalized:
            raise ValueError("broker_name is required")
        self._routes[asset_class] = normalized

    def adapter_for(self, asset_class: AssetClass) -> BrokerAdapter:
        try:
            broker_name = self._routes[asset_class]
        except KeyError as exc:
            message = f"no broker route configured for asset class: {asset_class.value}"
            raise KeyError(message) from exc
        return self._registry.get(broker_name)

    def connect_all(self) -> tuple[ManagedBrokerHealth, ...]:
        results: list[ManagedBrokerHealth] = []
        for name in self._registry.names():
            adapter = self._registry.get(name)
            adapter.connect()
            results.append(ManagedBrokerHealth(name, adapter.health_check()))
        return tuple(results)

    def health(self) -> tuple[ManagedBrokerHealth, ...]:
        return tuple(
            ManagedBrokerHealth(name, self._registry.get(name).health_check())
            for name in self._registry.names()
        )

    def submit(self, asset_class: AssetClass, order: OrderRequest) -> OrderReceipt:
        return self.adapter_for(asset_class).submit_order(order)
