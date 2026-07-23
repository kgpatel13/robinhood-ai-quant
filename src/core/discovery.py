from __future__ import annotations

import importlib
from collections.abc import Iterable
from types import ModuleType
from typing import Protocol, cast

from src.core.plugins import PluginRegistry


class PluginModule(Protocol):
    def register_plugins(self, registry: PluginRegistry) -> None: ...


def discover_plugins(registry: PluginRegistry, modules: Iterable[str]) -> list[str]:
    """Import plugin modules and call their explicit registration hook."""
    loaded: list[str] = []
    for module_name in modules:
        module: ModuleType = importlib.import_module(module_name)
        hook = getattr(module, "register_plugins", None)
        if not callable(hook):
            raise ValueError(f"Plugin module lacks register_plugins(): {module_name}")
        cast(PluginModule, module).register_plugins(registry)
        loaded.append(module_name)
    return loaded
