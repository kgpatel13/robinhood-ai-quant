from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RecoveryCheckpoint:
    sequence: int
    open_order_ids: tuple[str, ...]
    position_symbols: tuple[str, ...]
    metadata: dict[str, str]


class RecoveryStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, checkpoint: RecoveryCheckpoint) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(checkpoint), sort_keys=True), encoding="utf-8")
        temporary.replace(self._path)

    def load(self) -> RecoveryCheckpoint | None:
        if not self._path.exists():
            return None
        raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        return RecoveryCheckpoint(
            sequence=int(raw["sequence"]),
            open_order_ids=tuple(str(item) for item in raw["open_order_ids"]),
            position_symbols=tuple(str(item) for item in raw["position_symbols"]),
            metadata={str(key): str(value) for key, value in dict(raw["metadata"]).items()},
        )
