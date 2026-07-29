from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.alerting import AlertManager, ModelDriftRule, PlatformHaltedRule, RejectionRateRule
from src.audit_log import AuditEvent, JsonlAuditStore
from src.broker_reconciliation import (
    DiscrepancyType,
    ReconciliationDecision,
    ReconciliationDiscrepancy,
    ReconciliationReport,
)
from src.operations_dashboard import (
    ComponentHealth,
    ComponentState,
    ModelHealthSummary,
    OperationsDashboardService,
    PlatformState,
    SnapshotHistory,
    TradingMetrics,
)
from src.production_safety import SafetyDecision, SafetyState


def _metrics(rejection_rate: float = 0.0) -> TradingMetrics:
    return TradingMetrics(100_000.0, 100.0, 25_000.0, 10_000.0, 3, 2, 0.95, rejection_rate)


def _matched() -> ReconciliationReport:
    return ReconciliationReport(ReconciliationDecision.MATCHED, 0, ())


def test_snapshot_is_operational_when_all_gates_are_clear() -> None:
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(),
        safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
        reconciliation=_matched(),
    )
    assert snapshot.platform_state is PlatformState.OPERATIONAL
    assert snapshot.trading_allowed


def test_snapshot_is_degraded_for_warning_or_unknown_component() -> None:
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(),
        safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
        reconciliation=ReconciliationReport(ReconciliationDecision.WARNING, 1, ()),
        components=(ComponentHealth("market-data", ComponentState.UNKNOWN),),
    )
    assert snapshot.platform_state is PlatformState.DEGRADED
    assert snapshot.trading_allowed


def test_snapshot_halts_for_down_component() -> None:
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(),
        safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
        reconciliation=_matched(),
        components=(ComponentHealth("broker", ComponentState.DOWN, "connection lost"),),
    )
    assert snapshot.platform_state is PlatformState.HALTED
    assert not snapshot.trading_allowed


def test_snapshot_collects_unique_reasons() -> None:
    discrepancy = ReconciliationDiscrepancy(
        DiscrepancyType.CASH,
        "account",
        "cash mismatch",
        2,
    )
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(),
        safety=SafetyDecision(SafetyState.HALTED, 0.0, False, ("risk halt", "risk halt")),
        reconciliation=ReconciliationReport(ReconciliationDecision.HALT, 3, (discrepancy,)),
    )
    assert snapshot.reasons == ("risk halt", "cash mismatch")


def test_snapshot_history_is_bounded() -> None:
    service = OperationsDashboardService()
    history = SnapshotHistory(maximum_size=2)
    for pnl in (1.0, 2.0, 3.0):
        history.append(
            service.build_snapshot(
                metrics=TradingMetrics(100.0, pnl, 0.0, 0.0, 0, 0, 1.0, 0.0),
                safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
                reconciliation=_matched(),
            )
        )
    assert len(history.all()) == 2
    assert history.latest() is not None
    assert history.latest().metrics.daily_pnl == 3.0


def test_alert_manager_emits_matching_rules() -> None:
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(rejection_rate=0.4),
        safety=SafetyDecision(SafetyState.HALTED, 0.0, False, ("manual halt",)),
        reconciliation=_matched(),
        model_health=ModelHealthSummary(2, 1, 1),
    )
    manager = AlertManager(
        (PlatformHaltedRule(), RejectionRateRule(maximum_rate=0.2), ModelDriftRule())
    )
    alerts = manager.evaluate(snapshot, datetime(2026, 7, 29, tzinfo=UTC))
    assert {alert.rule_id for alert in alerts} == {
        "platform-halted",
        "high-order-rejection-rate",
        "model-drift",
    }


def test_alert_manager_applies_cooldown() -> None:
    snapshot = OperationsDashboardService().build_snapshot(
        metrics=_metrics(rejection_rate=0.5),
        safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
        reconciliation=_matched(),
    )
    manager = AlertManager((RejectionRateRule(),), timedelta(minutes=10))
    now = datetime(2026, 7, 29, tzinfo=UTC)
    assert len(manager.evaluate(snapshot, now)) == 1
    assert manager.evaluate(snapshot, now + timedelta(minutes=5)) == ()
    assert len(manager.evaluate(snapshot, now + timedelta(minutes=10))) == 1


def test_component_health_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ComponentHealth("broker", ComponentState.HEALTHY, observed_at=datetime(2026, 1, 1))


def test_trading_metrics_validate_rates() -> None:
    with pytest.raises(ValueError, match="fill_ratio"):
        TradingMetrics(100.0, 0.0, 0.0, 0.0, 0, 0, 1.1, 0.0)


def test_audit_store_round_trip(tmp_path) -> None:
    store = JsonlAuditStore(tmp_path / "audit" / "events.jsonl")
    event = AuditEvent(
        "evt-1",
        "execution.blocked",
        "atlas",
        datetime(2026, 7, 29, tzinfo=UTC),
        {"reason": "live disabled"},
    )
    store.append(event)
    records = store.read_all()
    assert len(records) == 1
    assert records[0]["event_id"] == "evt-1"
    assert records[0]["details"] == {"reason": "live disabled"}
