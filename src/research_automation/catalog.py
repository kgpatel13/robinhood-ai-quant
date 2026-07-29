from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from threading import Lock
from typing import Any

from src.research_automation.models import AutomationRun


class ResearchRunCatalog:
    """Append-only JSONL catalog for reproducible research automation runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def append(self, run: AutomationRun) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(run.to_dict(), sort_keys=True, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def entries(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        with self.path.open(encoding="utf-8") as handle:
            return tuple(json.loads(line) for line in handle if line.strip())

    def latest(self, run_id: str | None = None) -> dict[str, Any] | None:
        candidates: Iterable[dict[str, Any]] = self.entries()
        if run_id is not None:
            candidates = (item for item in candidates if item.get("run_id") == run_id)
        materialized = tuple(candidates)
        return materialized[-1] if materialized else None
