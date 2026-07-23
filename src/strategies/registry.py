from __future__ import annotations

from src.core.plugins import PluginDescriptor, PluginRegistry, PluginType
from src.strategies.base import Strategy
from src.strategies.moving_average import MovingAverageCrossStrategy

_REGISTRY = PluginRegistry()
_REGISTRY.register(
    PluginDescriptor("moving_average_cross", PluginType.STRATEGY, MovingAverageCrossStrategy)
)


def create_strategy(name: str, **parameters: int) -> Strategy:
    factory = _REGISTRY.resolve(PluginType.STRATEGY, name)
    strategy = factory(**parameters)
    if not isinstance(strategy, Strategy):
        raise TypeError(f"Strategy plugin {name} did not create a Strategy")
    return strategy


def available_strategies() -> list[str]:
    return _REGISTRY.names(PluginType.STRATEGY)
