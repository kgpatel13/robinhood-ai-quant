from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from .models import (
    DeploymentPolicy,
    DeploymentStage,
    HealthStatus,
    KillSwitchState,
    ProductionSnapshot,
    ServiceHealth,
)


class KillSwitch:
    def __init__(self) -> None:
        self._lock = RLock()
        self._state = KillSwitchState(engaged=False)

    @property
    def state(self) -> KillSwitchState:
        with self._lock:
            return self._state

    def engage(self, reason: str, actor: str = "system") -> KillSwitchState:
        if not reason.strip():
            raise ValueError("kill-switch reason is required")
        with self._lock:
            self._state = KillSwitchState(engaged=True, reason=reason, actor=actor)
            return self._state

    def reset(self, actor: str) -> KillSwitchState:
        if not actor.strip():
            raise ValueError("reset actor is required")
        with self._lock:
            self._state = KillSwitchState(engaged=False, actor=actor)
            return self._state


class ProductionController:
    def __init__(self, policy: DeploymentPolicy, kill_switch: KillSwitch | None = None) -> None:
        self._policy = policy
        self._kill_switch = kill_switch or KillSwitch()

    def evaluate(
        self,
        services: Iterable[ServiceHealth],
        *,
        reconciliation_clear: bool,
    ) -> ProductionSnapshot:
        health = {item.service: item for item in services}
        reasons: list[str] = []
        switch_state = self._kill_switch.state
        if switch_state.engaged:
            reasons.append(f"kill switch engaged: {switch_state.reason}")

        if self._policy.require_reconciliation and not reconciliation_clear:
            reasons.append("broker reconciliation is not clear")

        if self._policy.require_healthy_services:
            for service in sorted(self._policy.required_services):
                status = health.get(service)
                if status is None:
                    reasons.append(f"required service missing: {service}")
                elif status.status is not HealthStatus.HEALTHY:
                    reasons.append(f"required service unhealthy: {service}")

        stage = self._policy.stage
        if stage in {DeploymentStage.OFFLINE, DeploymentStage.HALTED}:
            reasons.append(f"deployment stage does not permit trading: {stage.value}")

        can_trade = not reasons
        capital_fraction = self._capital_fraction(stage) if can_trade else 0.0
        return ProductionSnapshot(
            stage=stage,
            can_trade=can_trade,
            capital_fraction=capital_fraction,
            kill_switch=switch_state,
            service_health=health,
            reasons=tuple(reasons),
        )

    def _capital_fraction(self, stage: DeploymentStage) -> float:
        if stage in {DeploymentStage.PAPER, DeploymentStage.SHADOW}:
            return 0.0
        if stage is DeploymentStage.CANARY:
            return self._policy.maximum_canary_capital_fraction
        if stage is DeploymentStage.PRODUCTION:
            return 1.0
        return 0.0
