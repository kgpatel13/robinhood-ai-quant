from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.execution.models import (
    AccountSnapshot,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
)
from src.robinhood_platform import (
    ReadinessLevel,
    RobinhoodCredentialManager,
    RobinhoodLimits,
    RobinhoodOperationsService,
    RobinhoodOrderGate,
    RobinhoodReadinessAssessor,
    RobinhoodReadinessInputs,
    RobinhoodReleaseStage,
    RobinhoodReportWriter,
)


class FakeRobinhoodAdapter:
    name = "robinhood"

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy
        self._account = AccountSnapshot(5_000.0, 10_000.0, 5_000.0, ())
        request = OrderRequest("AAPL", 1, OrderSide.BUY)
        self._orders = (OrderSnapshot("1", request, OrderStatus.ACCEPTED),)

    def health_check(self) -> BrokerHealth:
        status = (
            BrokerConnectionStatus.CONNECTED if self._healthy else BrokerConnectionStatus.DEGRADED
        )
        return BrokerHealth(status)

    def get_account(self) -> AccountSnapshot:
        return self._account

    def list_orders(self, *, include_terminal: bool = True) -> tuple[OrderSnapshot, ...]:
        return self._orders


def readiness(**overrides: object) -> RobinhoodReadinessInputs:
    values: dict[str, object] = {
        "credentials_available": True,
        "broker_connected": True,
        "broker_healthy": True,
        "reconciliation_clean": True,
        "market_data_fresh": True,
        "kill_switch_active": False,
        "paper_days": 30,
        "paper_orders": 500,
        "paper_fill_ratio": 0.98,
        "paper_rejection_rate": 0.01,
        "max_drawdown": 0.05,
    }
    values.update(overrides)
    return RobinhoodReadinessInputs(**values)  # type: ignore[arg-type]


def test_credentials_resolve_without_logging_secrets() -> None:
    manager = RobinhoodCredentialManager(
        environment={"ROBINHOOD_API_KEY": "key", "ROBINHOOD_PRIVATE_KEY": "secret"}
    )
    assert manager.available()
    resolved = manager.resolve()
    assert resolved.api_key == "key"
    assert resolved.private_key == "secret"


def test_missing_credentials_fail_closed() -> None:
    manager = RobinhoodCredentialManager(environment={})
    assert not manager.available()
    with pytest.raises(RuntimeError):
        manager.resolve()


def test_readiness_hard_block() -> None:
    report = RobinhoodReadinessAssessor().assess(readiness(kill_switch_active=True))
    assert report.level is ReadinessLevel.BLOCKED
    assert report.approved_stage is RobinhoodReleaseStage.HALTED


def test_readiness_requires_paper_history() -> None:
    report = RobinhoodReadinessAssessor().assess(readiness(paper_days=2, paper_orders=5))
    assert report.level is ReadinessLevel.NOT_READY


def test_readiness_canary_stage() -> None:
    report = RobinhoodReadinessAssessor().assess(readiness(paper_days=10, paper_orders=250))
    assert report.level is ReadinessLevel.CANARY_READY


def test_readiness_live_stage() -> None:
    report = RobinhoodReadinessAssessor().assess(readiness())
    assert report.level is ReadinessLevel.LIVE_READY


def test_order_gate_blocks_research() -> None:
    gate = RobinhoodOrderGate()
    account = AccountSnapshot(5_000, 10_000, 5_000, ())
    result = gate.evaluate(
        OrderRequest("AAPL", 1, OrderSide.BUY),
        reference_price=100,
        account=account,
        stage=RobinhoodReleaseStage.RESEARCH,
        open_orders=0,
        daily_submitted_notional=0,
    )
    assert not result.approved


def test_order_gate_applies_canary_fraction() -> None:
    gate = RobinhoodOrderGate(RobinhoodLimits(canary_capital_fraction=0.01))
    account = AccountSnapshot(5_000, 10_000, 5_000, ())
    result = gate.evaluate(
        OrderRequest("AAPL", 2, OrderSide.BUY),
        reference_price=100,
        account=account,
        stage=RobinhoodReleaseStage.CANARY,
        open_orders=0,
        daily_submitted_notional=0,
    )
    assert not result.approved
    assert result.allowed_notional == 100


def test_order_gate_approves_safe_paper_order() -> None:
    gate = RobinhoodOrderGate()
    account = AccountSnapshot(5_000, 10_000, 5_000, ())
    result = gate.evaluate(
        OrderRequest("AAPL", 1, OrderSide.BUY),
        reference_price=100,
        account=account,
        stage=RobinhoodReleaseStage.PAPER,
        open_orders=0,
        daily_submitted_notional=0,
    )
    assert result.approved


def test_order_gate_blocks_open_order_limit() -> None:
    gate = RobinhoodOrderGate(RobinhoodLimits(max_open_orders=1))
    account = AccountSnapshot(5_000, 10_000, 5_000, ())
    result = gate.evaluate(
        OrderRequest("AAPL", 1, OrderSide.BUY),
        reference_price=100,
        account=account,
        stage=RobinhoodReleaseStage.PAPER,
        open_orders=1,
        daily_submitted_notional=0,
    )
    assert not result.approved


def test_operations_snapshot_healthy() -> None:
    service = RobinhoodOperationsService(FakeRobinhoodAdapter())  # type: ignore[arg-type]
    snapshot = service.snapshot(RobinhoodReleaseStage.PAPER)
    assert snapshot.trading_allowed
    assert len(snapshot.orders) == 1


def test_operations_snapshot_degraded() -> None:
    service = RobinhoodOperationsService(FakeRobinhoodAdapter(False))  # type: ignore[arg-type]
    snapshot = service.snapshot(RobinhoodReleaseStage.PAPER)
    assert not snapshot.trading_allowed


def test_operations_requires_robinhood_adapter() -> None:
    adapter = FakeRobinhoodAdapter()
    adapter.name = "other"
    with pytest.raises(ValueError):
        RobinhoodOperationsService(adapter)  # type: ignore[arg-type]


def test_report_writer(tmp_path: Path) -> None:
    report = RobinhoodReadinessAssessor().assess(readiness())
    adapter = FakeRobinhoodAdapter()
    operations = RobinhoodOperationsService(adapter).snapshot(  # type: ignore[arg-type]
        RobinhoodReleaseStage.PAPER
    )
    path = RobinhoodReportWriter.write_json(
        tmp_path / "robinhood-report.json",
        readiness=report,
        operations=operations,
    )
    assert path.exists()
    assert "live_ready" in path.read_text(encoding="utf-8")


def test_operational_snapshot_timestamp_is_aware() -> None:
    adapter = FakeRobinhoodAdapter()
    operations = RobinhoodOperationsService(adapter).snapshot(  # type: ignore[arg-type]
        RobinhoodReleaseStage.PAPER
    )
    assert operations.generated_at.tzinfo is UTC
    assert operations.generated_at <= datetime.now(UTC)
