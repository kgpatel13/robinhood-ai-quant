from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from src.broker_reconciliation import (
    BrokerReconciliationEngine,
    BrokerStateCheckpoint,
    DiscrepancyType,
    ReconciliationDecision,
    ReconciliationPolicy,
)
from src.brokers import (
    AlpacaBrokerAdapter,
    BrokerConnectionStatus,
    BrokerError,
    BrokerRegistry,
    PaperBrokerAdapter,
    RobinhoodBrokerAdapter,
    TradingMode,
    TradingSafetyPolicy,
)
from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
    Position,
)
from src.execution.paper import PaperBroker


class FakeTransport:
    def __init__(self) -> None:
        self.connected = False
        self.orders: list[OrderSnapshot] = []
        self.account = AccountSnapshot(1_000.0, 1_000.0, 1_000.0, ())

    def connect(self) -> None:
        self.connected = True

    def health_check(self) -> Mapping[str, object]:
        return {"healthy": self.connected, "message": "ready"}

    def get_account(self) -> AccountSnapshot:
        return self.account

    def get_orders(self) -> Sequence[OrderSnapshot]:
        return tuple(self.orders)

    def get_fills(self, order_id: str | None = None) -> Sequence[Fill]:
        return ()

    def submit_order(self, order: OrderRequest) -> OrderSnapshot:
        snapshot = OrderSnapshot("remote-1", order, OrderStatus.ACCEPTED)
        self.orders.append(snapshot)
        return snapshot

    def cancel_order(self, order_id: str) -> bool:
        return any(order.order_id == order_id for order in self.orders)

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderSnapshot:
        return OrderSnapshot(order_id, order, OrderStatus.ACCEPTED, message="replaced")


def _account(cash: float, *positions: Position) -> AccountSnapshot:
    market_value = sum(position.market_value for position in positions)
    return AccountSnapshot(cash, cash + market_value, cash, tuple(positions))


def test_paper_adapter_health_and_positions() -> None:
    broker = PaperBroker(initial_cash=1_000.0, price_provider=lambda _: 10.0)
    adapter = PaperBrokerAdapter(broker)
    adapter.connect()
    assert adapter.health_check().healthy
    assert adapter.get_positions() == ()


def test_external_adapter_requires_connection() -> None:
    adapter = AlpacaBrokerAdapter(FakeTransport())
    with pytest.raises(BrokerError, match="not connected"):
        adapter.get_account()


def test_alpaca_paper_adapter_submits_after_connect() -> None:
    adapter = AlpacaBrokerAdapter(FakeTransport())
    adapter.connect()
    order = OrderRequest("AAPL", 1.0, OrderSide.BUY)
    receipt = adapter.submit_order(order)
    assert receipt.accepted
    assert receipt.order_id == "remote-1"
    assert adapter.health_check().status is BrokerConnectionStatus.CONNECTED


def test_live_robinhood_adapter_is_blocked_by_default() -> None:
    adapter = RobinhoodBrokerAdapter(FakeTransport(), mode=TradingMode.LIVE)
    adapter.connect()
    with pytest.raises(BrokerError, match="live order routing is disabled"):
        adapter.submit_order(OrderRequest("AAPL", 1.0, OrderSide.BUY))


def test_live_adapter_requires_explicit_safety_policy() -> None:
    policy = TradingSafetyPolicy(
        allowed_mode=TradingMode.LIVE,
        live_trading_enabled=True,
    )
    adapter = RobinhoodBrokerAdapter(
        FakeTransport(),
        mode=TradingMode.LIVE,
        safety_policy=policy,
    )
    adapter.connect()
    assert adapter.submit_order(OrderRequest("AAPL", 1.0, OrderSide.BUY)).accepted


def test_registry_rejects_duplicate_names() -> None:
    registry = BrokerRegistry()
    first = AlpacaBrokerAdapter(FakeTransport())
    registry.register(first)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(AlpacaBrokerAdapter(FakeTransport()))
    assert registry.get("ALPACA") is first
    assert registry.names() == ("alpaca",)


def test_reconciliation_matches_equal_accounts() -> None:
    account = _account(500.0, Position("AAPL", 2.0, 90.0, 100.0))
    report = BrokerReconciliationEngine().reconcile(account, account)
    assert report.decision is ReconciliationDecision.MATCHED
    assert report.trading_allowed


def test_reconciliation_warns_for_small_order_difference() -> None:
    account = _account(500.0)
    request = OrderRequest("AAPL", 1.0, OrderSide.BUY)
    order = OrderSnapshot("order-1", request, OrderStatus.ACCEPTED)
    report = BrokerReconciliationEngine().reconcile(
        account,
        account,
        local_orders=(order,),
    )
    assert report.decision is ReconciliationDecision.WARNING
    assert report.discrepancies[0].discrepancy_type is DiscrepancyType.ORDER_MISSING_BROKER


def test_reconciliation_halts_on_position_quantity_difference() -> None:
    local = _account(500.0, Position("AAPL", 3.0, 90.0, 100.0))
    broker = _account(500.0, Position("AAPL", 1.0, 90.0, 100.0))
    policy = ReconciliationPolicy(halt_score=2)
    report = BrokerReconciliationEngine(policy).reconcile(local, broker)
    assert report.decision is ReconciliationDecision.HALT
    assert not report.trading_allowed


def test_reconciliation_detects_cash_difference() -> None:
    report = BrokerReconciliationEngine().reconcile(_account(500.0), _account(450.0))
    assert any(
        item.discrepancy_type is DiscrepancyType.CASH
        for item in report.discrepancies
    )


def test_reconciliation_detects_duplicate_client_order_id() -> None:
    account = _account(500.0)
    request = OrderRequest("AAPL", 1.0, OrderSide.BUY, client_order_id="same")
    first = OrderSnapshot("one", request, OrderStatus.ACCEPTED)
    second = OrderSnapshot("two", request, OrderStatus.ACCEPTED)
    report = BrokerReconciliationEngine().reconcile(
        account,
        account,
        broker_orders=(first, second),
    )
    assert report.decision is ReconciliationDecision.HALT
    assert any(
        item.discrepancy_type is DiscrepancyType.DUPLICATE_CLIENT_ORDER_ID
        for item in report.discrepancies
    )


def test_checkpoint_round_trip(tmp_path) -> None:
    checkpoint = BrokerStateCheckpoint(tmp_path / "broker-state.json")
    assert checkpoint.load() is None
    checkpoint.save({"cash": 100.0, "orders": []})
    assert checkpoint.load() == {"cash": 100.0, "orders": []}


def test_alpaca_supports_order_replacement() -> None:
    adapter = AlpacaBrokerAdapter(FakeTransport())
    adapter.connect()
    order = OrderRequest("AAPL", 2.0, OrderSide.BUY)
    receipt = adapter.replace_order("remote-1", order)
    assert receipt.accepted
    assert receipt.message == "replaced"


def test_robinhood_replacement_is_unsupported() -> None:
    adapter = RobinhoodBrokerAdapter(FakeTransport())
    adapter.connect()
    with pytest.raises(RuntimeError, match="order_replacement"):
        adapter.replace_order(
            "remote-1",
            OrderRequest("AAPL", 2.0, OrderSide.BUY),
        )
