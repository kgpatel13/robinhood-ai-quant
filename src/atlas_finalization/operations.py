from __future__ import annotations

from dataclasses import dataclass

from src.atlas_finalization.models import (
    HealthSnapshot,
    OperationalAssessment,
    OperationStatus,
    PaperSessionMetrics,
)


class OperationalHealthAssessor:
    def assess(self, snapshot: HealthSnapshot) -> OperationalAssessment:
        hard_blocks = {
            "market data stale": not snapshot.market_data_fresh,
            "broker disconnected": not snapshot.broker_connected,
            "reconciliation mismatch": not snapshot.reconciliation_clean,
            "kill switch active": snapshot.kill_switch_active,
        }
        reasons = [reason for reason, blocked in hard_blocks.items() if blocked]
        if reasons:
            return OperationalAssessment(OperationStatus.HALTED, 0.0, tuple(reasons))

        score = 100.0
        score -= min(snapshot.error_rate * 200, 40)
        score -= min(snapshot.unresolved_alerts * 5, 25)
        if snapshot.decision_latency_ms > 2_000:
            score -= 10
            reasons.append("decision latency elevated")
        if snapshot.broker_latency_ms > 3_000:
            score -= 15
            reasons.append("broker latency elevated")
        score = round(max(0.0, score), 2)
        status = OperationStatus.HEALTHY if score >= 80 else OperationStatus.DEGRADED
        return OperationalAssessment(status, score, tuple(reasons))


@dataclass(frozen=True, slots=True)
class PaperReadinessPolicy:
    minimum_days: int = 60
    minimum_orders: int = 200
    minimum_fill_ratio: float = 0.90
    maximum_rejection_rate: float = 0.05
    maximum_drawdown: float = 0.15


class PaperReadinessEvaluator:
    def __init__(self, policy: PaperReadinessPolicy | None = None) -> None:
        self.policy = policy or PaperReadinessPolicy()

    def evaluate(self, metrics: PaperSessionMetrics) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if metrics.trading_days < self.policy.minimum_days:
            reasons.append("insufficient paper-trading days")
        if metrics.submitted_orders < self.policy.minimum_orders:
            reasons.append("insufficient paper orders")
        if metrics.fill_ratio < self.policy.minimum_fill_ratio:
            reasons.append("fill ratio below threshold")
        if metrics.rejection_rate > self.policy.maximum_rejection_rate:
            reasons.append("rejection rate above threshold")
        if metrics.maximum_drawdown > self.policy.maximum_drawdown:
            reasons.append("paper drawdown above threshold")
        if metrics.duplicate_orders:
            reasons.append("duplicate orders detected")
        if metrics.reconciliation_failures:
            reasons.append("reconciliation failures detected")
        return not reasons, tuple(reasons)
