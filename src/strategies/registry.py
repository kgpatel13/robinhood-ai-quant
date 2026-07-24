from __future__ import annotations

from collections.abc import Callable
from typing import cast

from src.strategies.atr_breakout import ATRBreakoutStrategy
from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter
from src.strategies.bollinger import BollingerMeanReversionStrategy
from src.strategies.donchian import DonchianBreakoutStrategy
from src.strategies.moving_average import MovingAverageCrossStrategy
from src.strategies.rsi import RSIMeanReversionStrategy
from src.strategies.turtle import TurtleTradingStrategy

StrategyFactory = Callable[..., Strategy]

_FACTORIES: dict[str, StrategyFactory] = {
    strategy.plugin_name: strategy
    for strategy in (
        MovingAverageCrossStrategy,
        RSIMeanReversionStrategy,
        DonchianBreakoutStrategy,
        TurtleTradingStrategy,
        BollingerMeanReversionStrategy,
        ATRBreakoutStrategy,
    )
}


def register_strategy(
    name: str,
    factory: StrategyFactory,
    *,
    replace: bool = False,
) -> None:
    if name in _FACTORIES and not replace:
        raise ValueError(f"Strategy already registered: {name}")
    _FACTORIES[name] = factory


def create_strategy(name: str, **parameters: int | float) -> Strategy:
    try:
        factory = _FACTORIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy: {name}") from exc

    strategy = factory(**parameters)
    strategy.validate_parameters()
    return strategy


def available_strategies() -> list[str]:
    return sorted(_FACTORIES)


def strategy_parameter_space(name: str) -> tuple[StrategyParameter, ...]:
    try:
        factory = _FACTORIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy: {name}") from exc

    parameter_space = cast(
        Callable[[], tuple[StrategyParameter, ...]],
        factory.parameter_space,  # type: ignore[attr-defined]
    )
    return parameter_space()


def strategy_defaults(name: str) -> dict[str, int | float]:
    try:
        factory = _FACTORIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy: {name}") from exc

    default_parameters = cast(
        Callable[[], dict[str, int | float]],
        factory.default_parameters,  # type: ignore[attr-defined]
    )
    return default_parameters()


def strategy_metadata(name: str) -> StrategyMetadata:
    strategy = create_strategy(name, **strategy_defaults(name))
    return strategy.metadata
