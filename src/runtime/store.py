from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from src.runtime.events import RuntimeEvent


class EventStore:
    """Append-only JSONL event journal with deterministic replay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: RuntimeEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def read(self) -> tuple[RuntimeEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[RuntimeEvent] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(RuntimeEvent.from_dict(json.loads(line)))
        return tuple(events)

    def replay(self, events: Iterable[RuntimeEvent] | None = None) -> tuple[RuntimeEvent, ...]:
        source = tuple(events) if events is not None else self.read()
        return tuple(sorted(source, key=lambda item: (item.created_at, item.event_id)))
