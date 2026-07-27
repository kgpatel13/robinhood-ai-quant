from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.execution.models import AccountSnapshot, Fill, OrderSnapshot


class ExecutionJournal:
    """SQLite journal for execution events, checkpoints, and account snapshots."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_entity
                    ON events(entity_id, created_at);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS heartbeats (
                    component TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _json_default(value: object) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return str(value.value)
        raise TypeError(f"cannot serialize {type(value)!r}")

    def append_event(
        self,
        *,
        event_id: str,
        event_type: str,
        entity_id: str,
        payload: Mapping[str, Any],
        created_at: datetime | None = None,
    ) -> bool:
        timestamp = (created_at or datetime.now(UTC)).isoformat()
        encoded = json.dumps(payload, default=self._json_default, sort_keys=True)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO events
                    (event_id, event_type, entity_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, event_type, entity_id, encoded, timestamp),
            )
            return cursor.rowcount == 1

    def record_order(self, order: OrderSnapshot) -> bool:
        return self.append_event(
            event_id=f"order:{order.order_id}:{order.status.value}:{order.updated_at.isoformat()}",
            event_type="order",
            entity_id=order.order_id,
            payload=asdict(order),
            created_at=order.updated_at,
        )

    def record_fill(self, fill: Fill) -> bool:
        return self.append_event(
            event_id=f"fill:{fill.fill_id}",
            event_type="fill",
            entity_id=fill.order_id,
            payload=asdict(fill),
            created_at=fill.timestamp,
        )

    def save_checkpoint(self, key: str, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(payload, default=self._json_default, sort_keys=True)
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO checkpoints(checkpoint_key, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(checkpoint_key) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (key, encoded, now),
            )

    def load_checkpoint(self, key: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM checkpoints WHERE checkpoint_key = ?", (key,)
            ).fetchone()
        return None if row is None else dict(json.loads(str(row["payload"])))

    def record_account_snapshot(self, account: AccountSnapshot) -> None:
        payload = json.dumps(asdict(account), default=self._json_default, sort_keys=True)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO account_snapshots(payload, created_at) VALUES (?, ?)",
                (payload, account.as_of.isoformat()),
            )

    def heartbeat(self, component: str, status: str, details: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO heartbeats(component, status, details, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(component) DO UPDATE SET
                    status=excluded.status,
                    details=excluded.details,
                    updated_at=excluded.updated_at
                """,
                (component, status, details, now),
            )

    def latest_heartbeat(self, component: str) -> tuple[str, str, datetime] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status, details, updated_at FROM heartbeats WHERE component = ?",
                (component,),
            ).fetchone()
        if row is None:
            return None
        return str(row["status"]), str(row["details"]), datetime.fromisoformat(row["updated_at"])
