from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from src.alerting.models import Alert
from src.alerting.rules import AlertRule
from src.operations_dashboard import OperationsSnapshot


class AlertManager:
    def __init__(
        self,
        rules: tuple[AlertRule, ...],
        cooldown: timedelta = timedelta(minutes=15),
    ) -> None:
        if cooldown < timedelta(0):
            raise ValueError("cooldown cannot be negative")
        self._rules = rules
        self._cooldown = cooldown
        self._last_emitted: dict[str, datetime] = {}

    def evaluate(
        self,
        snapshot: OperationsSnapshot,
        now: datetime | None = None,
    ) -> tuple[Alert, ...]:
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        alerts: list[Alert] = []
        for rule in self._rules:
            if not rule.matches(snapshot) or not self._cooldown_elapsed(rule.rule_id, observed_at):
                continue
            payload = f"{rule.rule_id}:{observed_at.isoformat()}"
            alert_id = sha256(payload.encode("utf-8")).hexdigest()[:20]
            alerts.append(
                Alert(
                    alert_id=alert_id,
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    title=rule.title,
                    message=rule.message(snapshot),
                    created_at=observed_at,
                )
            )
            self._last_emitted[rule.rule_id] = observed_at
        return tuple(alerts)

    def _cooldown_elapsed(self, rule_id: str, now: datetime) -> bool:
        previous = self._last_emitted.get(rule_id)
        return previous is None or now - previous >= self._cooldown
