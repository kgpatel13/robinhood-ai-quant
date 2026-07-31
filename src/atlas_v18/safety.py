from __future__ import annotations

from dataclasses import dataclass

from src.atlas_v18.models import SafetyDecision, SignalAction


@dataclass(frozen=True, slots=True)
class LiveSafetyState:
    kill_switch: bool = True
    manual_approval: bool = True
    approved: bool = False
    broker_healthy: bool = False
    duplicate_order: bool = False
    daily_pnl_pct: float = 0.0
    position_pct: float = 0.0
    total_exposure_pct: float = 0.0


class LiveSafetyLayer:
    def __init__(
        self,
        *,
        max_daily_loss_pct: float = 0.02,
        max_position_pct: float = 0.05,
        max_total_exposure_pct: float = 0.50,
    ) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_pct = max_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct

    def evaluate(self, action: SignalAction, state: LiveSafetyState) -> SafetyDecision:
        reasons: list[str] = []
        if action is SignalAction.WAIT:
            reasons.append("no executable signal")
        if state.kill_switch:
            reasons.append("kill switch enabled")
        if state.manual_approval and not state.approved:
            reasons.append("manual approval required")
        if not state.broker_healthy:
            reasons.append("broker heartbeat unhealthy")
        if state.duplicate_order:
            reasons.append("duplicate order detected")
        if state.daily_pnl_pct <= -self.max_daily_loss_pct:
            reasons.append("daily loss limit reached")
        if state.position_pct > self.max_position_pct:
            reasons.append("position limit exceeded")
        if state.total_exposure_pct > self.max_total_exposure_pct:
            reasons.append("portfolio exposure limit exceeded")
        return SafetyDecision(allowed=not reasons, reasons=tuple(reasons))
