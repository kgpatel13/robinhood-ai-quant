"""Core extensibility and application infrastructure."""

from src.core.context import ExecutionContext
from src.core.discovery import discover_plugins
from src.core.events import Event, EventBus
from src.core.metrics import MetricsCollector, Timer
from src.core.plugins import PluginDescriptor, PluginRegistry, PluginType
from src.core.services import ServiceContainer

__all__ = [
    "Event",
    "EventBus",
    "ExecutionContext",
    "discover_plugins",
    "MetricsCollector",
    "PluginDescriptor",
    "PluginRegistry",
    "PluginType",
    "ServiceContainer",
    "Timer",
]
