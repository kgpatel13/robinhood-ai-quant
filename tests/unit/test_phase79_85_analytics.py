from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from src.analytics import (
    EquityJournal,
    EquitySnapshot,
    compare_benchmark,
    rolling_metrics,
    summarize_equity,
    trade_replay,
)
from src.paper_trading import (
    AutomatedPaperConfig,
    AutomatedPaperTrader,
    MarketQuote,
    PaperAccount,
    PaperAccountStore,
    PaperBroker,
    PaperBrokerConfig,
    StaticSignalDataProvider,
)
from src.strategies.registry import create_strategy, strategy_defaults


def _bars(trending: bool = True) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=300, freq="D", tz="UTC")
    if trending:
        close = pd.Series([100.0 + index_value for index_value in range(300)], index=index)
    else:
        close = pd.Series([200.0 - index_value for index_value in range(300)], index=index)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


def _quote(symbol: str, price: float, moment: datetime) -> MarketQuote:
    return MarketQuote(symbol, moment, price - 0.01, price + 0.01, price, "static")


def test_equity_journal_and_summary(tmp_path) -> None:
    journal = EquityJournal(tmp_path / "equity.jsonl")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index, equity in enumerate((100_000.0, 101_000.0, 99_000.0, 104_000.0)):
        journal.append(
            EquitySnapshot(start + timedelta(days=index), equity, equity, 0.0, 0.0, 0.0, 0)
        )
    frame = journal.load()
    summary = summarize_equity(frame["equity"])
    assert len(frame) == 4
    assert summary.total_return == pytest.approx(0.04)
    assert summary.maximum_drawdown < 0
    assert "drawdown" in rolling_metrics(frame["equity"], window=2)


def test_benchmark_comparison() -> None:
    index = pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC")
    portfolio = pd.Series([100.0, 102.0, 104.0, 108.0], index=index)
    benchmark = pd.Series([100.0, 101.0, 102.01, 103.0301], index=index)
    comparison = compare_benchmark(portfolio, benchmark)
    assert comparison.excess_return > 0
    assert -1.0 <= comparison.correlation <= 1.0


def test_automated_paper_cycle_enters_and_journals(tmp_path) -> None:
    moment = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)
    account = PaperAccount(starting_cash=100_000.0, cash=100_000.0)
    broker = PaperBroker(account, PaperBrokerConfig(maximum_order_notional=20_000.0))
    store = PaperAccountStore(tmp_path / "account.json")
    journal = EquityJournal(tmp_path / "equity.jsonl")
    strategy = create_strategy("moving_average_cross", **strategy_defaults("moving_average_cross"))
    trader = AutomatedPaperTrader(
        AutomatedPaperConfig(("SPY",), "moving_average_cross", minimum_history=60),
        strategy,
        StaticSignalDataProvider({"SPY": _bars()}),
        broker,
        store,
        journal,
    )
    result = trader.cycle({"SPY": _quote("SPY", 200.0, moment)}, moment)
    assert len(result.orders) == 1
    assert result.open_positions == 1
    assert store.load(100_000.0).positions["SPY"].quantity > 0
    assert len(journal.load()) == 1


def test_automated_cycle_respects_position_limit(tmp_path) -> None:
    moment = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)
    account = PaperAccount(starting_cash=100_000.0, cash=100_000.0)
    broker = PaperBroker(account)
    store = PaperAccountStore(tmp_path / "account.json")
    strategy = create_strategy("moving_average_cross", **strategy_defaults("moving_average_cross"))
    trader = AutomatedPaperTrader(
        AutomatedPaperConfig(
            ("SPY", "QQQ"),
            "moving_average_cross",
            maximum_open_positions=1,
            minimum_history=60,
        ),
        strategy,
        StaticSignalDataProvider({"SPY": _bars(), "QQQ": _bars()}),
        broker,
        store,
        EquityJournal(tmp_path / "equity.jsonl"),
    )
    result = trader.cycle(
        {"SPY": _quote("SPY", 200.0, moment), "QQQ": _quote("QQQ", 300.0, moment)},
        moment,
    )
    assert result.open_positions == 1
    assert "maximum open positions reached" in result.rejected.values()


def test_trade_replay_empty_account() -> None:
    replay = trade_replay(PaperAccount(starting_cash=1_000.0, cash=1_000.0))
    assert replay.empty
