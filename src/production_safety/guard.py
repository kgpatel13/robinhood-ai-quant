from __future__ import annotations

from src.production_safety.models import (
    SafetyDecision,
    SafetyPolicy,
    SafetyState,
    SafetyTelemetry,
)


class ProductionSafetyGuard:
    """Independent kill-switch and throttling layer for paper or future live execution."""

    def __init__(self, policy: SafetyPolicy | None = None) -> None:
        self.policy = policy or SafetyPolicy()

    def evaluate(self, telemetry: SafetyTelemetry) -> SafetyDecision:
        reasons: list[str] = []
        drawdown = 1.0 - telemetry.current_equity / telemetry.peak_equity

        if telemetry.manual_kill_switch:
            reasons.append("manual_kill_switch_enabled")
        if not telemetry.broker_connected:
            reasons.append("broker_disconnected")
        if telemetry.data_age_seconds > self.policy.maximum_data_age_seconds:
            reasons.append("market_data_stale")
        if telemetry.daily_pnl <= -self.policy.maximum_daily_loss:
            reasons.append("daily_loss_limit_breached")
        if drawdown >= self.policy.maximum_drawdown:
            reasons.append("drawdown_limit_breached")

        if reasons:
            return SafetyDecision(SafetyState.HALTED, 0.0, False, tuple(reasons))

        throttle_reasons: list[str] = []
        if telemetry.consecutive_losses >= self.policy.maximum_consecutive_losses:
            throttle_reasons.append("consecutive_loss_limit_reached")
        if telemetry.order_rejection_rate >= self.policy.maximum_order_rejection_rate:
            throttle_reasons.append("order_rejection_rate_elevated")
        if throttle_reasons:
            return SafetyDecision(
                SafetyState.THROTTLED,
                0.25,
                True,
                tuple(throttle_reasons),
            )
        return SafetyDecision(SafetyState.ARMED, 1.0, True, ())
