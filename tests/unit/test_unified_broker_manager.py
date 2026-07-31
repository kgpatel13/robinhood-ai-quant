from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.brokers.manager import AssetClass, BrokerRoute, UnifiedBrokerManager
from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.brokers.safety import TradingMode
from src.execution.models import AccountSnapshot, OrderReceipt, OrderRequest, OrderSide


@dataclass
class StubAdapter:
    name: str
    mode: TradingMode = TradingMode.PAPER
    capabilities: object = object()
    connected: bool = False

    def connect(self) -> None:
        self.connected = True

    def health_check(self) -> BrokerHealth:
        return BrokerHealth(BrokerConnectionStatus.CONNECTED, "ok")

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        return OrderReceipt("order-1", True, client_order_id=order.client_order_id)

    def cancel_order(self, order_id: str) -> bool:
        return bool(order_id)

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderReceipt:
        return self.submit_order(order)

    def get_order(self, order_id: str):
        return None

    def list_orders(self, *, include_terminal: bool = True):
        return ()

    def list_fills(self, order_id: str | None = None):
        return ()

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(100.0, 100.0, 100.0, ())

    def get_positions(self):
        return ()


def test_manager_routes_orders_by_asset_class() -> None:
    adapter = StubAdapter("paper")
    manager = UnifiedBrokerManager(routes=[BrokerRoute(AssetClass.CRYPTO, "paper")])
    manager.register(adapter)

    receipt = manager.submit(
        AssetClass.CRYPTO,
        OrderRequest("BTC-USD", 0.001, OrderSide.BUY),
    )

    assert receipt.accepted
    assert receipt.order_id == "order-1"


def test_manager_connects_and_reports_all_registered_adapters() -> None:
    first = StubAdapter("first")
    second = StubAdapter("second")
    manager = UnifiedBrokerManager()
    manager.register(first)
    manager.register(second)

    results = manager.connect_all()

    assert first.connected and second.connected
    assert [result.broker_name for result in results] == ["first", "second"]
    assert all(result.health.healthy for result in results)


def test_manager_fails_closed_when_route_is_missing() -> None:
    manager = UnifiedBrokerManager()
    with pytest.raises(KeyError, match="no broker route configured"):
        manager.adapter_for(AssetClass.EQUITY)
