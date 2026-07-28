from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import uuid4


class EventPriority(int, Enum):
    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100


class EventType(StrEnum):
    MARKET_DATA = "market_data"
    SIGNAL = "signal"
    RISK = "risk"
    ORDER = "order"
    FILL = "fill"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    HEARTBEAT = "heartbeat"
    SYSTEM_ALERT = "system_alert"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: str = field(default_factory=lambda: uuid4().hex)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "atlas"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "payload": self.payload,
            "priority": int(self.priority),
            "correlation_id": self.correlation_id,
            "event_id": self.event_id,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RuntimeEvent:
        return cls(
            event_type=EventType(str(value["event_type"])),
            payload=dict(value.get("payload", {})),
            priority=EventPriority(int(value.get("priority", EventPriority.NORMAL))),
            correlation_id=str(value["correlation_id"]),
            event_id=str(value["event_id"]),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            source=str(value.get("source", "atlas")),
        )
