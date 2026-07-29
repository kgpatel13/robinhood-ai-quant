from __future__ import annotations

from src.feature_store.models import FeatureMetadata


class FeatureRegistry:
    def __init__(self) -> None:
        self._items: dict[str, FeatureMetadata] = {}

    def register(self, metadata: FeatureMetadata) -> None:
        if metadata.identifier in self._items:
            raise ValueError(f"feature set already registered: {metadata.identifier}")
        self._items[metadata.identifier] = metadata

    def get(self, identifier: str) -> FeatureMetadata:
        try:
            return self._items[identifier]
        except KeyError as exc:
            raise KeyError(f"unknown feature set: {identifier}") from exc

    def list_all(self) -> tuple[FeatureMetadata, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
