from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from src.research.phase8.models import CandidateDefinition


class ExperimentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    output_root TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    experiment_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (experiment_id, candidate_id)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    experiment_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT,
                    PRIMARY KEY (experiment_id, name)
                );
                """
            )

    def create_experiment(
        self, experiment_id: str, config: dict[str, object], output_root: Path
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?)",
                (
                    experiment_id,
                    datetime.now(UTC).isoformat(),
                    "RUNNING",
                    json.dumps(config, sort_keys=True, default=str),
                    str(output_root),
                ),
            )

    def set_experiment_status(self, experiment_id: str, status: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE experiments SET status = ? WHERE experiment_id = ?",
                (status, experiment_id),
            )

    def candidate_status(self, experiment_id: str, candidate_id: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM candidates WHERE experiment_id = ? AND candidate_id = ?",
                (experiment_id, candidate_id),
            ).fetchone()
        return None if row is None else str(row["status"])

    def upsert_candidate(
        self,
        experiment_id: str,
        candidate: CandidateDefinition,
        status: str,
        error: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id, candidate_id) DO UPDATE SET
                    status = excluded.status,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    experiment_id,
                    candidate.candidate_id,
                    candidate.strategy,
                    json.dumps(candidate.parameters, sort_keys=True),
                    candidate.source,
                    status,
                    error,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def add_artifact(self, experiment_id: str, name: str, path: Path, sha256: str = "") -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO artifacts VALUES (?, ?, ?, ?)",
                (experiment_id, name, str(path), sha256),
            )
