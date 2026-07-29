from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from src.operations_dashboard.models import OperationsSnapshot


class SnapshotHistory:
    def __init__(self, maximum_size: int = 1_000) -> None:
        if maximum_size < 1:
            raise ValueError("maximum_size must be positive")
        self._items: deque[OperationsSnapshot] = deque(maxlen=maximum_size)

    def append(self, snapshot: OperationsSnapshot) -> None:
        self._items.append(snapshot)

    def extend(self, snapshots: Iterable[OperationsSnapshot]) -> None:
        self._items.extend(snapshots)

    def latest(self) -> OperationsSnapshot | None:
        return self._items[-1] if self._items else None

    def all(self) -> tuple[OperationsSnapshot, ...]:
        return tuple(self._items)
