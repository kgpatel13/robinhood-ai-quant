from __future__ import annotations

import sys
from types import ModuleType

import pytest

from src.core.discovery import discover_plugins
from src.core.plugins import PluginDescriptor, PluginRegistry, PluginType


def test_discover_plugins_calls_registration_hook() -> None:
    module = ModuleType("test_demo_plugin")

    def register_plugins(registry: PluginRegistry) -> None:
        registry.register(PluginDescriptor("demo", PluginType.INDICATOR, object()))

    module.register_plugins = register_plugins  # type: ignore[attr-defined]
    sys.modules[module.__name__] = module
    registry = PluginRegistry()
    try:
        assert discover_plugins(registry, [module.__name__]) == [module.__name__]
        assert registry.names(PluginType.INDICATOR) == ["demo"]
    finally:
        sys.modules.pop(module.__name__, None)


def test_discover_plugins_requires_hook() -> None:
    module = ModuleType("test_invalid_plugin")
    sys.modules[module.__name__] = module
    try:
        with pytest.raises(ValueError, match="register_plugins"):
            discover_plugins(PluginRegistry(), [module.__name__])
    finally:
        sys.modules.pop(module.__name__, None)
