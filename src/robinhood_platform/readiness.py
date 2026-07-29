from __future__ import annotations

from src.robinhood_platform.models import (
    ReadinessLevel,
    RobinhoodReadinessInputs,
    RobinhoodReadinessReport,
    RobinhoodReleaseStage,
)


class RobinhoodReadinessAssessor:
    def assess(self, inputs: RobinhoodReadinessInputs) -> RobinhoodReadinessReport:
        reasons: list[str] = []
        hard_blocks = {
            "credentials unavailable": not inputs.credentials_available,
            "broker disconnected": not inputs.broker_connected,
            "broker unhealthy": not inputs.broker_healthy,
            "reconciliation mismatch": not inputs.reconciliation_clean,
            "market data stale": not inputs.market_data_fresh,
            "kill switch active": inputs.kill_switch_active,
        }
        reasons.extend(reason for reason, blocked in hard_blocks.items() if blocked)
        if reasons:
            return RobinhoodReadinessReport(
                level=ReadinessLevel.BLOCKED,
                score=0.0,
                approved_stage=RobinhoodReleaseStage.HALTED,
                reasons=tuple(reasons),
            )

        score = 40.0
        score += min(inputs.paper_days, 30) / 30 * 15
        score += min(inputs.paper_orders, 500) / 500 * 15
        score += inputs.paper_fill_ratio * 15
        score += max(0.0, 1 - inputs.paper_rejection_rate * 5) * 5
        score += max(0.0, 1 - inputs.max_drawdown / 0.20) * 10
        score -= min(inputs.unresolved_alerts * 5, 20)
        score = round(max(0.0, min(score, 100.0)), 2)

        if inputs.paper_days < 5 or inputs.paper_orders < 25:
            reasons.append("insufficient paper-trading history")
            level = ReadinessLevel.NOT_READY
            stage = RobinhoodReleaseStage.RESEARCH
        elif score < 75:
            reasons.append("paper metrics below canary threshold")
            level = ReadinessLevel.PAPER_READY
            stage = RobinhoodReleaseStage.PAPER
        elif inputs.paper_days < 20 or inputs.paper_orders < 200:
            reasons.append("more observation time required before live readiness")
            level = ReadinessLevel.CANARY_READY
            stage = RobinhoodReleaseStage.CANARY
        else:
            level = ReadinessLevel.LIVE_READY
            stage = RobinhoodReleaseStage.LIVE

        return RobinhoodReadinessReport(level, score, stage, tuple(reasons))
