from __future__ import annotations

from datetime import UTC, datetime

from src.broker_reconciliation import ReconciliationDecision, ReconciliationReport
from src.operations_dashboard.models import (
    ComponentHealth,
    ComponentState,
    ModelHealthSummary,
    OperationsSnapshot,
    PlatformState,
    TradingMetrics,
)
from src.production_safety import SafetyDecision, SafetyState


class OperationsDashboardService:
    """Builds a broker-independent, UI-ready operations snapshot."""

    def build_snapshot(
        self,
        *,
        metrics: TradingMetrics,
        safety: SafetyDecision,
        reconciliation: ReconciliationReport,
        components: tuple[ComponentHealth, ...] = (),
        model_health: ModelHealthSummary | None = None,
        generated_at: datetime | None = None,
    ) -> OperationsSnapshot:
        reasons = list(safety.reasons)
        reasons.extend(item.message for item in reconciliation.discrepancies)

        component_down = any(item.state is ComponentState.DOWN for item in components)
        component_degraded = any(
            item.state in {ComponentState.DEGRADED, ComponentState.UNKNOWN}
            for item in components
        )
        halted = (
            safety.state is SafetyState.HALTED
            or reconciliation.decision is ReconciliationDecision.HALT
            or component_down
        )
        degraded = (
            safety.state is SafetyState.THROTTLED
            or reconciliation.decision is ReconciliationDecision.WARNING
            or component_degraded
        )

        if halted:
            platform_state = PlatformState.HALTED
        elif degraded:
            platform_state = PlatformState.DEGRADED
        else:
            platform_state = PlatformState.OPERATIONAL

        trading_allowed = (
            platform_state is not PlatformState.HALTED
            and safety.allow_new_orders
            and reconciliation.trading_allowed
        )
        return OperationsSnapshot(
            generated_at=generated_at or datetime.now(UTC),
            platform_state=platform_state,
            trading_allowed=trading_allowed,
            metrics=metrics,
            components=components,
            model_health=model_health or ModelHealthSummary(),
            reasons=tuple(dict.fromkeys(reason for reason in reasons if reason)),
        )
