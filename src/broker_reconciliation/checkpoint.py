from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class BrokerStateCheckpoint:
    """Atomic JSON checkpoint storage for restart recovery."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: dict[str, object]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(state, sort_keys=True, default=str), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("broker checkpoint must contain a JSON object")
        return raw
