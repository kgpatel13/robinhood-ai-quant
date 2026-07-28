from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.paper_trading import (
    MarketQuote,
    PaperAccount,
    PaperAccountStore,
    PaperBroker,
    PaperBrokerConfig,
    PaperOrderRequest,
    PaperOrderSide,
    PaperOrderStatus,
    PaperSessionConfig,
    RealMarketPaperSession,
    SessionStatus,
    StaticMarketDataFeed,
    build_daily_report,
)


def quote(
    symbol: str = "SPY", price: float = 500.0, timestamp: datetime | None = None
) -> MarketQuote:
    return MarketQuote(
        symbol, timestamp or datetime.now(UTC), price - 0.05, price + 0.05, price, "test"
    )


def test_paper_broker_buy_sell_and_realized_pnl() -> None:
    account = PaperAccount(100_000.0, 100_000.0)
    broker = PaperBroker(
        account, PaperBrokerConfig(slippage_bps=0.0, maximum_order_notional=100_000.0)
    )
    now = datetime.now(UTC)
    buy = broker.submit(
        PaperOrderRequest("1", "SPY", PaperOrderSide.BUY, 10, now, "trend"), quote()
    )
    assert buy.status == PaperOrderStatus.FILLED
    sell = broker.submit(
        PaperOrderRequest("2", "SPY", PaperOrderSide.SELL, 10, now, "trend"), quote(price=510.0)
    )
    assert sell.status == PaperOrderStatus.FILLED
    assert account.realized_pnl > 0
    assert not account.positions


def test_duplicate_order_is_rejected() -> None:
    account = PaperAccount(10_000.0, 10_000.0)
    broker = PaperBroker(account)
    request = PaperOrderRequest("same", "SPY", PaperOrderSide.BUY, 1, datetime.now(UTC), "test")
    broker.submit(request, quote())
    duplicate = broker.submit(request, quote())
    assert duplicate.status == PaperOrderStatus.REJECTED
    assert "duplicate" in duplicate.reason


def test_account_store_round_trip(tmp_path: Path) -> None:
    store = PaperAccountStore(tmp_path / "account.json")
    account = PaperAccount(10_000.0, 9_500.0)
    broker = PaperBroker(account, PaperBrokerConfig(slippage_bps=0.0))
    broker.submit(
        PaperOrderRequest("1", "SPY", PaperOrderSide.BUY, 1, datetime.now(UTC), "trend"), quote()
    )
    store.save(account)
    restored = store.load(10_000.0)
    assert restored.cash == account.cash
    assert restored.positions["SPY"].quantity == 1


def test_stale_quote_halts_session(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    feed = StaticMarketDataFeed({"SPY": quote(timestamp=now - timedelta(minutes=10))})
    account = PaperAccount(10_000.0, 10_000.0)
    session = RealMarketPaperSession(
        PaperSessionConfig(("SPY",), stale_quote_seconds=60),
        feed,
        PaperBroker(account),
        PaperAccountStore(tmp_path / "state.json"),
    )
    session.start()
    snapshot = session.cycle(now)
    assert snapshot.status == SessionStatus.HALTED
    assert any("stale" in message for message in snapshot.messages)


def test_daily_report_contains_summary() -> None:
    account = PaperAccount(10_000.0, 10_000.0)
    report = build_daily_report(account, datetime.now(UTC))
    assert report.summary["equity"] == 10_000.0
    assert report.summary["open_positions"] == 0
