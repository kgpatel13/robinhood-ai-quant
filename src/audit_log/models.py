from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    actor: str
    occurred_at: datetime
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type or not self.actor:
            raise ValueError("audit identifiers cannot be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
