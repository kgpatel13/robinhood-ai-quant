from __future__ import annotations

import pytest

from src.core.plugins import PluginDescriptor, PluginError, PluginRegistry, PluginType


def test_register_resolve_and_list_plugin() -> None:
    registry = PluginRegistry()
    implementation = object()
    registry.register(PluginDescriptor("demo", PluginType.STRATEGY, implementation))
    assert registry.resolve(PluginType.STRATEGY, "demo") is implementation
    assert registry.names(PluginType.STRATEGY) == ["demo"]


def test_duplicate_plugin_is_rejected() -> None:
    registry = PluginRegistry()
    descriptor = PluginDescriptor("demo", PluginType.STRATEGY, object())
    registry.register(descriptor)
    with pytest.raises(PluginError, match="already registered"):
        registry.register(descriptor)


def test_replace_plugin() -> None:
    registry = PluginRegistry()
    first, second = object(), object()
    registry.register(PluginDescriptor("demo", PluginType.STRATEGY, first))
    registry.register(PluginDescriptor("demo", PluginType.STRATEGY, second), replace=True)
    assert registry.resolve(PluginType.STRATEGY, "demo") is second


def test_disabled_plugin_cannot_resolve() -> None:
    registry = PluginRegistry()
    registry.register(PluginDescriptor("demo", PluginType.BROKER, object(), enabled=False))
    with pytest.raises(PluginError, match="disabled"):
        registry.resolve(PluginType.BROKER, "demo")


def test_unregister_unknown_plugin_fails() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginError, match="Unknown plugin"):
        registry.unregister(PluginType.AI_MODEL, "missing")
