from pathlib import Path

from src.execution.models import OrderRequest, OrderSide
from src.shadow_trading import ShadowExecutionConfig, ShadowExecutionEngine
from src.trading_ledger import SQLiteTradingLedger, build_performance_snapshot


def test_shadow_buy_persists_and_recovers(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    ledger = SQLiteTradingLedger(path, starting_cash=1_000.0)
    engine = ShadowExecutionEngine(
        ledger=ledger,
        quote_provider=lambda _symbol: 100.0,
        config=ShadowExecutionConfig(slippage_bps=0.0, max_order_notional=500.0),
    )

    receipt = engine.submit(
        OrderRequest(symbol="BTC-USD", quantity=2.0, side=OrderSide.BUY),
        strategy="test",
    )

    assert receipt.accepted is True
    recovered = SQLiteTradingLedger(path, starting_cash=999_999.0)
    summary = recovered.summary({"BTC-USD": 110.0})
    assert summary.starting_cash == 1_000.0
    assert summary.cash == 800.0
    assert summary.market_value == 220.0
    assert summary.equity == 1_020.0
    assert summary.unrealized_pnl == 20.0
    assert summary.order_count == 1
    assert summary.fill_count == 1


def test_shadow_round_trip_calculates_realized_pnl(tmp_path: Path) -> None:
    prices = iter((100.0, 120.0))
    ledger = SQLiteTradingLedger(tmp_path / "ledger.db", starting_cash=1_000.0)
    engine = ShadowExecutionEngine(
        ledger=ledger,
        quote_provider=lambda _symbol: next(prices),
        config=ShadowExecutionConfig(slippage_bps=0.0, max_order_notional=500.0),
    )
    assert engine.submit(OrderRequest("BTC-USD", 2.0, OrderSide.BUY)).accepted
    assert engine.submit(OrderRequest("BTC-USD", 2.0, OrderSide.SELL)).accepted

    summary = ledger.summary()
    performance = build_performance_snapshot(summary)
    assert summary.cash == 1_040.0
    assert summary.realized_pnl == 40.0
    assert summary.equity == 1_040.0
    assert performance.net_pnl == 40.0
    assert performance.return_pct == 4.0


def test_shadow_rejects_order_above_notional_limit(tmp_path: Path) -> None:
    ledger = SQLiteTradingLedger(tmp_path / "ledger.db", starting_cash=10_000.0)
    engine = ShadowExecutionEngine(
        ledger=ledger,
        quote_provider=lambda _symbol: 100.0,
        config=ShadowExecutionConfig(max_order_notional=50.0),
    )
    receipt = engine.submit(OrderRequest("BTC-USD", 1.0, OrderSide.BUY))
    assert receipt.accepted is False
    assert ledger.summary().fill_count == 0
    assert ledger.summary().order_count == 1
