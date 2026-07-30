from __future__ import annotations

from dataclasses import dataclass

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.brokers.safety import TradingMode
from src.execution.models import (
    AccountSnapshot,
    OrderReceipt,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
)
from src.live_execution import (
    ExecutionContext,
    ExecutionDecision,
    ExecutionPolicy,
    ExecutionRecoveryManager,
    IdempotencyRegistry,
    LiveExecutionEngine,
)


@dataclass
class StubBroker:
    mode: TradingMode = TradingMode.PAPER
    name: str = "stub"
    capabilities: BrokerCapabilities = BrokerCapabilities(paper_trading=True)

    def __post_init__(self) -> None:
        self.orders: list[OrderSnapshot] = []

    def connect(self) -> None:
        return None

    def health_check(self) -> BrokerHealth:
        return BrokerHealth(BrokerConnectionStatus.CONNECTED)

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        order_id = f"order-{len(self.orders) + 1}"
        self.orders.append(OrderSnapshot(order_id, order, OrderStatus.ACCEPTED))
        return OrderReceipt(order_id, True, client_order_id=order.client_order_id)

    def cancel_order(self, order_id: str) -> bool:
        return True

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderReceipt:
        return OrderReceipt(order_id, True, client_order_id=order.client_order_id)

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        return next((item for item in self.orders if item.order_id == order_id), None)

    def list_orders(self, *, include_terminal: bool = True) -> tuple[OrderSnapshot, ...]:
        orders = self.orders if include_terminal else [o for o in self.orders if not o.terminal]
        return tuple(orders)

    def list_fills(self, order_id: str | None = None) -> tuple[()]:
        return ()

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(1_000, 1_000, 1_000, ())

    def get_positions(self) -> tuple[()]:
        return ()


def request(client_order_id: str = "client-1") -> OrderRequest:
    return OrderRequest("AAPL", 10, OrderSide.BUY, client_order_id=client_order_id)


def test_accepts_paper_order() -> None:
    engine = LiveExecutionEngine(StubBroker())
    result = engine.submit(request(), ExecutionContext(100.0))
    assert result.decision is ExecutionDecision.ACCEPTED
    assert result.order_id == "order-1"


def test_blocks_duplicate_order() -> None:
    engine = LiveExecutionEngine(StubBroker())
    context = ExecutionContext(100.0)
    assert engine.submit(request(), context).decision is ExecutionDecision.ACCEPTED
    assert engine.submit(request(), context).decision is ExecutionDecision.DUPLICATE


def test_blocks_live_mode_by_default() -> None:
    broker = StubBroker(mode=TradingMode.LIVE)
    engine = LiveExecutionEngine(broker)
    result = engine.submit(request(), ExecutionContext(100.0))
    assert result.message == "live_trading_disabled"


def test_blocks_failed_reconciliation() -> None:
    engine = LiveExecutionEngine(StubBroker())
    result = engine.submit(request(), ExecutionContext(100.0, reconciliation_clear=False))
    assert result.decision is ExecutionDecision.BLOCKED


def test_blocks_excessive_notional() -> None:
    policy = ExecutionPolicy(maximum_order_notional=500.0)
    engine = LiveExecutionEngine(StubBroker(), policy=policy)
    result = engine.submit(request(), ExecutionContext(100.0))
    assert result.message == "maximum_order_notional_exceeded"


def test_applies_size_multiplier() -> None:
    engine = LiveExecutionEngine(StubBroker())
    result = engine.submit(request(), ExecutionContext(100.0, size_multiplier=0.25))
    assert result.request.quantity == 2.5


def test_recovery_restores_idempotency_keys() -> None:
    broker = StubBroker()
    broker.submit_order(request())
    registry = IdempotencyRegistry()
    report = ExecutionRecoveryManager(broker, registry).recover()
    assert report.active_order_ids == ("order-1",)
    assert registry.contains("client-1")
