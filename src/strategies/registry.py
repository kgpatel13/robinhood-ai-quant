from __future__ import annotations

from collections.abc import Callable

from src.strategies.base import Strategy
from src.strategies.moving_average import MovingAverageCrossStrategy

StrategyFactory = Callable[..., Strategy]

_STRATEGIES: dict[str, StrategyFactory] = {
    "moving_average_cross": MovingAverageCrossStrategy,
}


def create_strategy(name: str, **parameters: int) -> Strategy:
    try:
        factory = _STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {name}. Available: {sorted(_STRATEGIES)}") from exc
    return factory(**parameters)


def available_strategies() -> list[str]:
    return sorted(_STRATEGIES)
