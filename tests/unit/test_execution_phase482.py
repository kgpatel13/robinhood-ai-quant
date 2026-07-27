from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from src.execution import (
    DailyPaperTradingOrchestrator,
    DailyWorkflowConfig,
    DataRefreshResult,
    ExecutionJournal,
    MarketSession,
    OrderRouter,
    PaperBroker,
    PaperTradingRuntime,
    TargetPortfolio,
)
from src.execution.models import AccountSnapshot


@dataclass
class StubRefresher:
    calls: int = 0

    def refresh(self, as_of: datetime) -> DataRefreshResult:
        self.calls += 1
        return DataRefreshResult(True, 42, as_of.date().isoformat())


@dataclass
class StubTargets:
    weights: dict[str, float]
    calls: int = 0

    def generate(self, as_of: datetime, account: AccountSnapshot) -> TargetPortfolio:
        self.calls += 1
        assert account.equity > 0
        return TargetPortfolio(self.weights, "test-model", as_of.date().isoformat())


def _build(tmp_path, targets: dict[str, float], *, require_market_open: bool = True):
    price_map = {"AAPL": 100.0, "MSFT": 200.0}
    broker = PaperBroker(initial_cash=10_000, price_provider=price_map.__getitem__)
    journal = ExecutionJournal(tmp_path / "execution.sqlite3")
    runtime = PaperTradingRuntime(broker, journal)
    refresher = StubRefresher()
    provider = StubTargets(targets)
    reports = []
    orchestrator = DailyPaperTradingOrchestrator(
        runtime=runtime,
        router=OrderRouter(broker),
        data_refresher=refresher,
        target_provider=provider,
        price_provider=lambda symbols, _now: {symbol: price_map[symbol] for symbol in symbols},
        session=MarketSession(),
        config=DailyWorkflowConfig(
            min_notional=1.0,
            require_market_open=require_market_open,
        ),
        reporter=reports.append,
    )
    return orchestrator, broker, refresher, provider, reports


def test_daily_workflow_refreshes_builds_orders_executes_and_checkpoints(tmp_path) -> None:
    orchestrator, broker, refresher, provider, reports = _build(
        tmp_path, {"AAPL": 0.50, "MSFT": 0.25}
    )
    now = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)

    result = orchestrator.run(now)

    assert result.status == "COMPLETED"
    assert result.rows_updated == 42
    assert result.model_name == "test-model"
    assert result.planned_orders == 2
    assert result.accepted_orders == 2
    assert result.rejected_orders == 0
    assert refresher.calls == provider.calls == 1
    assert len(reports) == 1
    account = broker.get_account()
    assert account.cash == pytest.approx(2_500)
    assert {position.symbol for position in account.positions} == {"AAPL", "MSFT"}
    assert orchestrator.runtime.journal.load_checkpoint("daily-paper-workflow:2026-07-28")


def test_daily_workflow_is_idempotent_without_force(tmp_path) -> None:
    orchestrator, broker, refresher, provider, _ = _build(tmp_path, {"AAPL": 0.50})
    now = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)

    first = orchestrator.run(now)
    second = orchestrator.run(now)

    assert first.status == "COMPLETED"
    assert second.status == "SKIPPED_ALREADY_COMPLETED"
    assert refresher.calls == provider.calls == 1
    assert len(broker.list_orders()) == 1


def test_force_allows_same_day_rerun_without_duplicate_fills(tmp_path) -> None:
    orchestrator, broker, refresher, provider, _ = _build(tmp_path, {"AAPL": 0.50})
    now = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)

    orchestrator.run(now)
    forced = orchestrator.run(now, force=True)

    assert forced.status == "COMPLETED"
    assert forced.planned_orders == 0
    assert refresher.calls == provider.calls == 2
    assert len(broker.list_fills()) == 1


def test_closed_market_skips_before_external_work(tmp_path) -> None:
    orchestrator, _broker, refresher, provider, reports = _build(tmp_path, {"AAPL": 0.50})

    result = orchestrator.run(datetime(2026, 7, 28, 22, 0, tzinfo=UTC))

    assert result.status == "SKIPPED_MARKET_CLOSED"
    assert refresher.calls == provider.calls == 0
    assert reports == [result]


def test_non_trading_day_skips_even_when_market_open_not_required(tmp_path) -> None:
    orchestrator, _broker, refresher, provider, _ = _build(
        tmp_path, {"AAPL": 0.50}, require_market_open=False
    )

    result = orchestrator.run(datetime(2026, 7, 26, 15, 0, tzinfo=UTC))

    assert result.status == "SKIPPED_NON_TRADING_DAY"
    assert refresher.calls == provider.calls == 0


def test_missing_price_is_reported_as_ignored_symbol(tmp_path) -> None:
    price_map = {"AAPL": 100.0}
    broker = PaperBroker(initial_cash=10_000, price_provider=price_map.__getitem__)
    runtime = PaperTradingRuntime(broker, ExecutionJournal(tmp_path / "execution.sqlite3"))
    orchestrator = DailyPaperTradingOrchestrator(
        runtime=runtime,
        router=OrderRouter(broker),
        data_refresher=StubRefresher(),
        target_provider=StubTargets({"AAPL": 0.50, "MSFT": 0.25}),
        price_provider=lambda _symbols, _now: price_map,
        config=DailyWorkflowConfig(min_notional=1.0),
    )

    result = orchestrator.run(datetime(2026, 7, 28, 15, 0, tzinfo=UTC))

    assert result.status == "COMPLETED"
    assert result.ignored_symbols == ("MSFT",)
    assert result.planned_orders == 1


def test_failure_sets_failed_heartbeat(tmp_path) -> None:
    orchestrator, _broker, _refresher, _provider, _ = _build(tmp_path, {"AAPL": 0.50})
    orchestrator.price_provider = lambda _symbols, _now: (_ for _ in ()).throw(RuntimeError("feed"))

    with pytest.raises(RuntimeError, match="feed"):
        orchestrator.run(datetime(2026, 7, 28, 15, 0, tzinfo=UTC))

    heartbeat = orchestrator.runtime.journal.latest_heartbeat("daily-paper-orchestrator")
    assert heartbeat is not None
    assert heartbeat[0] == "failed"
    assert "RuntimeError:feed" in heartbeat[1]
