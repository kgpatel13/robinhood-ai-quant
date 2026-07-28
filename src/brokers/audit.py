from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class BrokerAuditEvent:
    event_id: str
    event_type: str
    broker: str
    entity_id: str
    payload: dict[str, Any]
    created_at: datetime


class BrokerAuditLog:
    """Append-only JSONL audit trail for broker-facing operations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append(
        self,
        *,
        event_type: str,
        broker: str,
        entity_id: str,
        payload: dict[str, Any] | None = None,
    ) -> BrokerAuditEvent:
        event = BrokerAuditEvent(
            event_id=uuid4().hex,
            event_type=event_type,
            broker=broker,
            entity_id=entity_id,
            payload=dict(payload or {}),
            created_at=datetime.now(UTC),
        )
        row = asdict(event)
        row["created_at"] = event.created_at.isoformat()
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return event

    def read_all(self) -> list[BrokerAuditEvent]:
        if not self.path.exists():
            return []
        events: list[BrokerAuditEvent] = []
        with self._lock, self.path.open(encoding="utf-8") as handle:
            for line in handle:
                raw = json.loads(line)
                events.append(
                    BrokerAuditEvent(
                        event_id=str(raw["event_id"]),
                        event_type=str(raw["event_type"]),
                        broker=str(raw["broker"]),
                        entity_id=str(raw["entity_id"]),
                        payload=dict(raw.get("payload", {})),
                        created_at=datetime.fromisoformat(str(raw["created_at"])),
                    )
                )
        return events
