from __future__ import annotations

from threading import Lock


class IdempotencyRegistry:
    """Thread-safe registry preventing duplicate client-order submissions."""

    def __init__(self) -> None:
        self._keys: set[str] = set()
        self._lock = Lock()

    def reserve(self, key: str) -> bool:
        normalized = key.strip()
        if not normalized:
            raise ValueError("idempotency key is required")
        with self._lock:
            if normalized in self._keys:
                return False
            self._keys.add(normalized)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._keys.discard(key.strip())

    def contains(self, key: str) -> bool:
        with self._lock:
            return key.strip() in self._keys
