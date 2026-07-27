from __future__ import annotations

from src.execution import (
    BrokerManager,
    ExecutionMonitor,
    OrderRequest,
    OrderRouter,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperBroker,
    PortfolioSync,
)


def prices(symbol: str) -> float:
    return {"AAPL": 100.0, "MSFT": 200.0}[symbol]


def test_paper_broker_market_buy_sell_and_accounting() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=prices, commission_per_order=1)
    buy = broker.submit_order(OrderRequest("aapl", 10, OrderSide.BUY))
    assert buy.accepted
    assert broker.get_order(buy.order_id).status is OrderStatus.FILLED  # type: ignore[union-attr]
    account = broker.get_account()
    assert account.cash == 8_999
    assert account.positions[0].quantity == 10

    sell = broker.submit_order(OrderRequest("AAPL", 4, OrderSide.SELL))
    assert sell.accepted
    account = broker.get_account()
    assert account.cash == 9_398
    assert account.positions[0].quantity == 6


def test_duplicate_client_order_id_is_idempotent() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    request = OrderRequest("AAPL", 1, OrderSide.BUY, client_order_id="same")
    first = broker.submit_order(request)
    second = broker.submit_order(request)
    assert first.order_id == second.order_id
    assert broker.get_account().positions[0].quantity == 1


def test_limit_order_rests_then_fills() -> None:
    current = {"AAPL": 100.0}
    broker = PaperBroker(initial_cash=10_000, price_provider=lambda symbol: current[symbol])
    receipt = broker.submit_order(
        OrderRequest("AAPL", 2, OrderSide.BUY, OrderType.LIMIT, limit_price=95)
    )
    assert receipt.accepted
    assert broker.get_order(receipt.order_id).status is OrderStatus.ACCEPTED  # type: ignore[union-attr]
    current["AAPL"] = 94
    assert broker.process_open_orders() == 1
    assert broker.get_order(receipt.order_id).status is OrderStatus.FILLED  # type: ignore[union-attr]


def test_cancel_open_order() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    receipt = broker.submit_order(
        OrderRequest("AAPL", 2, OrderSide.BUY, OrderType.LIMIT, limit_price=90)
    )
    assert broker.cancel_order(receipt.order_id)
    assert broker.get_order(receipt.order_id).status is OrderStatus.CANCELLED  # type: ignore[union-attr]


def test_insufficient_buying_power_rejected() -> None:
    broker = PaperBroker(initial_cash=50, price_provider=prices)
    receipt = broker.submit_order(OrderRequest("AAPL", 1, OrderSide.BUY))
    assert not receipt.accepted
    assert broker.get_order(receipt.order_id).status is OrderStatus.REJECTED  # type: ignore[union-attr]


def test_router_manager_monitor_and_reconciliation() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    manager = BrokerManager()
    manager.register(broker, make_active=True)
    router = OrderRouter(manager.active)
    receipt = router.submit(OrderRequest("MSFT", 2, OrderSide.BUY, client_order_id="route-1"))
    assert receipt.accepted
    assert (
        router.submit(OrderRequest("MSFT", 2, OrderSide.BUY, client_order_id="route-1")) == receipt
    )
    summary = ExecutionMonitor(broker).summary()
    assert summary.filled_orders == 1
    assert PortfolioSync.reconcile({"MSFT": 2}, broker.get_account()).in_sync
    assert not PortfolioSync.reconcile({"MSFT": 3}, broker.get_account()).in_sync
