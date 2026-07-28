from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CheckpointManager:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, state: dict[str, Any]) -> Path:
        target = self.directory / f"{name}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(target)
        return target

    def load(self, name: str) -> dict[str, Any] | None:
        target = self.directory / f"{name}.json"
        if not target.exists():
            return None
        loaded = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("checkpoint root must be an object")
        return loaded
