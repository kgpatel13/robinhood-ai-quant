from __future__ import annotations

from dataclasses import dataclass

from src.trading_ledger.models import LedgerSummary


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    net_pnl: float
    return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    cash_utilization_pct: float
    order_count: int
    fill_count: int


def build_performance_snapshot(summary: LedgerSummary) -> PerformanceSnapshot:
    net_pnl = summary.equity - summary.starting_cash
    return_pct = 100.0 * net_pnl / summary.starting_cash
    cash_utilization_pct = 100.0 * summary.market_value / summary.equity if summary.equity else 0.0
    return PerformanceSnapshot(
        net_pnl=net_pnl,
        return_pct=return_pct,
        realized_pnl=summary.realized_pnl,
        unrealized_pnl=summary.unrealized_pnl,
        cash_utilization_pct=cash_utilization_pct,
        order_count=summary.order_count,
        fill_count=summary.fill_count,
    )
