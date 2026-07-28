from __future__ import annotations

from pathlib import Path

import pytest

from src.brokers import (
    BrokerAuditLog,
    BrokerError,
    BrokerErrorCategory,
    BrokerOrderRouter,
    BrokerRetryPolicy,
    PaperBrokerAdapter,
    TradingMode,
    TradingSafetyPolicy,
)
from src.execution import OrderRequest, OrderSide, PaperBroker


def test_paper_adapter_is_idempotent_and_audited(tmp_path: Path) -> None:
    audit = BrokerAuditLog(tmp_path / "broker.jsonl")
    broker = PaperBroker(initial_cash=10_000, price_provider=lambda _symbol: 100.0)
    adapter = PaperBrokerAdapter(broker, audit_log=audit)
    router = BrokerOrderRouter(adapter)
    order = OrderRequest("AAPL", 2, OrderSide.BUY, client_order_id="phase10-idem")

    first = router.submit(order)
    second = router.submit(order)

    assert first == second
    assert first.accepted
    assert len(adapter.list_orders()) == 1
    assert adapter.get_account().equity == pytest.approx(10_000.0)
    assert [event.event_type for event in audit.read_all()] == [
        "order_submitted",
        "account_snapshot",
    ]


def test_live_trading_is_hard_blocked_by_default() -> None:
    policy = TradingSafetyPolicy()
    with pytest.raises(BrokerError) as caught:
        policy.validate(TradingMode.LIVE, adapter_supports_live=True)
    assert caught.value.info.category is BrokerErrorCategory.SAFETY_BLOCK


def test_router_retries_transient_failures() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=lambda _symbol: 50.0)
    adapter = PaperBrokerAdapter(broker)
    attempts = 0
    original = adapter.submit_order

    def flaky(order: OrderRequest):  # type: ignore[no-untyped-def]
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary timeout")
        return original(order)

    adapter.submit_order = flaky  # type: ignore[method-assign]
    router = BrokerOrderRouter(adapter, retry_policy=BrokerRetryPolicy(max_attempts=3))

    receipt = router.submit(OrderRequest("MSFT", 1, OrderSide.BUY, client_order_id="retry"))

    assert receipt.accepted
    assert attempts == 3


def test_nonretryable_failure_returns_rejected_receipt() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=lambda _symbol: 50.0)
    adapter = PaperBrokerAdapter(broker)

    def invalid(_order: OrderRequest):  # type: ignore[no-untyped-def]
        raise ValueError("bad order")

    adapter.submit_order = invalid  # type: ignore[method-assign]
    router = BrokerOrderRouter(adapter, retry_policy=BrokerRetryPolicy(max_attempts=5))

    receipt = router.submit(OrderRequest("MSFT", 1, OrderSide.BUY, client_order_id="invalid"))

    assert not receipt.accepted
    assert receipt.message == "bad order"
