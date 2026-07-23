from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.common.exceptions import QuantPlatformError


class PluginError(QuantPlatformError):
    """Raised when plugin registration or resolution fails."""


class PluginType(StrEnum):
    STRATEGY = "strategy"
    INDICATOR = "indicator"
    DATA_PROVIDER = "data_provider"
    ALLOCATOR = "allocator"
    REPORTER = "reporter"
    BROKER = "broker"
    RISK_MODEL = "risk_model"
    AI_MODEL = "ai_model"
    OPTIMIZER = "optimizer"
    OBJECTIVE = "objective"


@dataclass(frozen=True)
class PluginDescriptor[T]:
    name: str
    plugin_type: PluginType
    implementation: T
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[PluginType, dict[str, PluginDescriptor[Any]]] = {}

    def register(self, descriptor: PluginDescriptor[Any], *, replace: bool = False) -> None:
        bucket = self._plugins.setdefault(descriptor.plugin_type, {})
        if descriptor.name in bucket and not replace:
            raise PluginError(
                f"Plugin already registered: {descriptor.plugin_type.value}:{descriptor.name}"
            )
        bucket[descriptor.name] = descriptor

    def unregister(self, plugin_type: PluginType, name: str) -> None:
        bucket = self._plugins.get(plugin_type, {})
        if name not in bucket:
            raise PluginError(f"Unknown plugin: {plugin_type.value}:{name}")
        del bucket[name]

    def get(self, plugin_type: PluginType, name: str) -> PluginDescriptor[Any]:
        descriptor = self._plugins.get(plugin_type, {}).get(name)
        if descriptor is None:
            raise PluginError(f"Unknown plugin: {plugin_type.value}:{name}")
        if not descriptor.enabled:
            raise PluginError(f"Plugin is disabled: {plugin_type.value}:{name}")
        return descriptor

    def resolve(self, plugin_type: PluginType, name: str) -> Any:
        return self.get(plugin_type, name).implementation

    def list(self, plugin_type: PluginType | None = None) -> builtins.list[PluginDescriptor[Any]]:
        if plugin_type is not None:
            return sorted(self._plugins.get(plugin_type, {}).values(), key=lambda item: item.name)
        return sorted(
            (item for bucket in self._plugins.values() for item in bucket.values()),
            key=lambda item: (item.plugin_type.value, item.name),
        )

    def names(self, plugin_type: PluginType) -> builtins.list[str]:
        return [item.name for item in self.list(plugin_type)]
