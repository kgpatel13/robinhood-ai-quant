from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from src.operations_dashboard import (
    ComponentHealth,
    ComponentState,
    ModelHealthSummary,
    OperationsDashboardService,
    TradingMetrics,
)
from src.broker_reconciliation import (
    ReconciliationDecision,
    ReconciliationReport,
)
from src.production_safety import SafetyDecision, SafetyState


def _demo_snapshot():
    service = OperationsDashboardService()
    return service.build_snapshot(
        metrics=TradingMetrics(
            equity=100_000.0,
            daily_pnl=0.0,
            gross_exposure=0.0,
            net_exposure=0.0,
            open_positions=0,
            open_orders=0,
            fill_ratio=1.0,
            rejection_rate=0.0,
        ),
        safety=SafetyDecision(SafetyState.ARMED, 1.0, True, ()),
        reconciliation=ReconciliationReport(ReconciliationDecision.MATCHED, 0, ()),
        components=(
            ComponentHealth(
                "paper-broker",
                ComponentState.HEALTHY,
                "Connected in paper mode",
                datetime.now(UTC),
            ),
        ),
        model_health=ModelHealthSummary(),
    )


def main() -> None:
    st.set_page_config(page_title="Atlas Operations", layout="wide")
    st.title("Atlas Operations Console")
    st.caption("Read-only operational view. Live trading remains disabled by default.")
    snapshot = _demo_snapshot()

    status_columns = st.columns(4)
    status_columns[0].metric("Platform", snapshot.platform_state.value.upper())
    status_columns[1].metric("Equity", f"${snapshot.metrics.equity:,.2f}")
    status_columns[2].metric("Daily P&L", f"${snapshot.metrics.daily_pnl:,.2f}")
    status_columns[3].metric("Open Orders", snapshot.metrics.open_orders)

    st.subheader("Safety and execution")
    st.write(
        {
            "trading_allowed": snapshot.trading_allowed,
            "gross_exposure": snapshot.metrics.gross_exposure,
            "net_exposure": snapshot.metrics.net_exposure,
            "fill_ratio": snapshot.metrics.fill_ratio,
            "rejection_rate": snapshot.metrics.rejection_rate,
        }
    )

    st.subheader("Components")
    st.dataframe(
        [
            {
                "component": item.name,
                "state": item.state.value,
                "message": item.message,
                "latency_ms": item.latency_ms,
            }
            for item in snapshot.components
        ],
        use_container_width=True,
    )

    if snapshot.reasons:
        st.subheader("Operational reasons")
        for reason in snapshot.reasons:
            st.warning(reason)


if __name__ == "__main__":
    main()
