from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    rule_id: str
    severity: AlertSeverity
    title: str
    message: str
    created_at: datetime
    state: AlertState = AlertState.OPEN
    labels: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.alert_id or not self.rule_id or not self.title:
            raise ValueError("alert identifiers and title cannot be empty")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
