from __future__ import annotations

from datetime import UTC, date, datetime

from src.execution import (
    ExecutionJournal,
    MarketSession,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperBroker,
    PaperTradingRuntime,
    RebalancePlanner,
)


def prices(symbol: str) -> float:
    return {"AAPL": 100.0, "MSFT": 200.0}[symbol]


def test_checkpoint_and_restart_recovery(tmp_path) -> None:
    journal = ExecutionJournal(tmp_path / "execution.sqlite3")
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    receipt = broker.submit_order(OrderRequest("AAPL", 10, OrderSide.BUY))
    runtime = PaperTradingRuntime(broker, journal)
    runtime.checkpoint()

    recovered = PaperBroker(initial_cash=1, price_provider=prices)
    recovered_runtime = PaperTradingRuntime(recovered, journal)
    assert recovered_runtime.recover()
    recovered_order = recovered.get_order(receipt.order_id)
    assert recovered_order is not None
    assert recovered_order.status is OrderStatus.FILLED
    assert recovered.get_account().cash == 9_000
    assert recovered.get_account().positions[0].quantity == 10
    assert len(recovered.list_fills()) == 1


def test_checkpoint_is_idempotent(tmp_path) -> None:
    journal = ExecutionJournal(tmp_path / "execution.sqlite3")
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    broker.submit_order(OrderRequest("AAPL", 1, OrderSide.BUY))
    runtime = PaperTradingRuntime(broker, journal)
    runtime.checkpoint()
    runtime.checkpoint()

    with journal._connection() as connection:  # noqa: SLF001 - verifies persisted contract
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert event_count == 2  # one order state and one fill


def test_market_session_weekend_holiday_and_hours() -> None:
    session = MarketSession(holidays=frozenset({date(2026, 7, 27)}))
    assert not session.is_open(datetime(2026, 7, 27, 15, 0, tzinfo=UTC))
    assert not session.is_open(datetime(2026, 7, 26, 15, 0, tzinfo=UTC))
    assert session.is_open(datetime(2026, 7, 28, 15, 0, tzinfo=UTC))
    assert not session.is_open(datetime(2026, 7, 28, 22, 0, tzinfo=UTC))


def test_runtime_only_processes_orders_during_market_hours(tmp_path) -> None:
    current = {"AAPL": 100.0}
    broker = PaperBroker(initial_cash=10_000, price_provider=lambda symbol: current[symbol])
    receipt = broker.submit_order(
        OrderRequest("AAPL", 2, OrderSide.BUY, OrderType.LIMIT, limit_price=95)
    )
    current["AAPL"] = 94
    runtime = PaperTradingRuntime(broker, ExecutionJournal(tmp_path / "runtime.sqlite3"))

    closed = runtime.run_cycle(datetime(2026, 7, 28, 22, 0, tzinfo=UTC))
    assert closed.fills_processed == 0
    resting_order = broker.get_order(receipt.order_id)
    assert resting_order is not None
    assert resting_order.status is OrderStatus.ACCEPTED

    opened = runtime.run_cycle(datetime(2026, 7, 28, 15, 0, tzinfo=UTC))
    assert opened.fills_processed == 1
    filled_order = broker.get_order(receipt.order_id)
    assert filled_order is not None
    assert filled_order.status is OrderStatus.FILLED


def test_rebalance_planner_sells_before_buys() -> None:
    broker = PaperBroker(initial_cash=10_000, price_provider=prices)
    broker.submit_order(OrderRequest("AAPL", 50, OrderSide.BUY))
    plan = RebalancePlanner.plan(
        {"AAPL": 0.25, "MSFT": 0.50},
        broker.get_account(),
        {"AAPL": 100.0, "MSFT": 200.0},
    )
    assert [order.side for order in plan.orders] == [OrderSide.SELL, OrderSide.BUY]
    assert plan.orders[0].symbol == "AAPL"
    assert plan.orders[1].symbol == "MSFT"


def test_heartbeat_is_persisted(tmp_path) -> None:
    journal = ExecutionJournal(tmp_path / "execution.sqlite3")
    journal.heartbeat("paper-runtime", "healthy", "ok")
    heartbeat = journal.latest_heartbeat("paper-runtime")
    assert heartbeat is not None
    assert heartbeat[:2] == ("healthy", "ok")
