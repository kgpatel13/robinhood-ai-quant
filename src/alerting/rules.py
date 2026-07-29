from __future__ import annotations

from dataclasses import dataclass

from src.alerting.models import AlertSeverity
from src.operations_dashboard import OperationsSnapshot, PlatformState


@dataclass(frozen=True, slots=True)
class AlertRule:
    rule_id: str
    title: str
    severity: AlertSeverity

    def matches(self, snapshot: OperationsSnapshot) -> bool:
        raise NotImplementedError

    def message(self, snapshot: OperationsSnapshot) -> str:
        return "; ".join(snapshot.reasons) or self.title


@dataclass(frozen=True, slots=True)
class PlatformHaltedRule(AlertRule):
    rule_id: str = "platform-halted"
    title: str = "Atlas trading platform halted"
    severity: AlertSeverity = AlertSeverity.CRITICAL

    def matches(self, snapshot: OperationsSnapshot) -> bool:
        return snapshot.platform_state is PlatformState.HALTED


@dataclass(frozen=True, slots=True)
class RejectionRateRule(AlertRule):
    maximum_rate: float = 0.20
    rule_id: str = "high-order-rejection-rate"
    title: str = "Order rejection rate is elevated"
    severity: AlertSeverity = AlertSeverity.WARNING

    def __post_init__(self) -> None:
        if not 0.0 <= self.maximum_rate <= 1.0:
            raise ValueError("maximum_rate must be in [0, 1]")

    def matches(self, snapshot: OperationsSnapshot) -> bool:
        return snapshot.metrics.rejection_rate > self.maximum_rate

    def message(self, snapshot: OperationsSnapshot) -> str:
        rate = snapshot.metrics.rejection_rate
        return f"Order rejection rate {rate:.2%} exceeds {self.maximum_rate:.2%}."


@dataclass(frozen=True, slots=True)
class ModelDriftRule(AlertRule):
    rule_id: str = "model-drift"
    title: str = "Model drift requires review"
    severity: AlertSeverity = AlertSeverity.WARNING

    def matches(self, snapshot: OperationsSnapshot) -> bool:
        return snapshot.model_health.drifting_models > 0

    def message(self, snapshot: OperationsSnapshot) -> str:
        count = snapshot.model_health.drifting_models
        return f"{count} active model(s) show drift."
