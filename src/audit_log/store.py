from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from src.audit_log.models import AuditEvent


class JsonlAuditStore:
    """Append-only audit store with flush and fsync durability."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def append(self, event: AuditEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = asdict(event)
        record["occurred_at"] = event.occurred_at.isoformat()
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_all(self) -> tuple[dict[str, object], ...]:
        if not self._path.exists():
            return ()
        records: list[dict[str, object]] = []
        with self._path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(value)
        return tuple(records)
