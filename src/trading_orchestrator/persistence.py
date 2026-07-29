from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from threading import Lock


class CycleAuditStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def append(self, record: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(record), sort_keys=True, separators=(",", ":"), default=str)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_all(self) -> tuple[dict[str, object], ...]:
        if not self._path.exists():
            return ()
        with self._path.open(encoding="utf-8") as handle:
            return tuple(json.loads(line) for line in handle if line.strip())


class AtomicCycleStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, state: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        temp.write_text(json.dumps(dict(state), sort_keys=True, default=str), encoding="utf-8")
        os.replace(temp, self._path)

    def load(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        value = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("cycle state must be a JSON object")
        return value
