from __future__ import annotations

from collections.abc import Iterable

from src.alpha_intelligence.models import StrategyDefinition


class StrategyRegistry:
    """In-memory strategy catalog with explicit version identity."""

    def __init__(self, definitions: Iterable[StrategyDefinition] = ()) -> None:
        self._definitions: dict[tuple[str, str], StrategyDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: StrategyDefinition) -> None:
        key = (definition.strategy_id, definition.version)
        if key in self._definitions:
            raise ValueError(f"strategy version already registered: {key}")
        self._definitions[key] = definition

    def get(self, strategy_id: str, version: str | None = None) -> StrategyDefinition:
        matches = [
            definition
            for (registered_id, _), definition in self._definitions.items()
            if registered_id == strategy_id
        ]
        if not matches:
            raise KeyError(strategy_id)
        if version is not None:
            key = (strategy_id, version)
            if key not in self._definitions:
                raise KeyError(key)
            return self._definitions[key]
        return sorted(matches, key=lambda item: item.version)[-1]

    def list(self) -> tuple[StrategyDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda item: (item.name, item.version)))
