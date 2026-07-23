from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    command: str = "unknown"
    environment: str = "development"

    @classmethod
    def create(cls, command: str, environment: str) -> ExecutionContext:
        return cls(command=command, environment=environment)
