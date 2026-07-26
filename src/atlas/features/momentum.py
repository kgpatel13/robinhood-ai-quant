from __future__ import annotations

from src.atlas.features.calculations import pct_return, rolling_max, rolling_min, rsi
from src.atlas.features.core import (
    FeatureContext,
    FeatureFunction,
    FeatureRegistry,
    register_feature,
)


def register(registry: FeatureRegistry) -> None:
    for period in (1, 5, 10, 20, 60, 120, 252):
        register_feature(
            registry,
            name=f"return_{period}d",
            category="momentum",
            description=f"Percentage return over {period} bars.",
            window=period,
            compute=_make_return(period),
        )
    for period in (7, 14, 21, 28):
        register_feature(
            registry,
            name=f"rsi_{period}",
            category="momentum",
            description=f"Relative Strength Index over {period} bars.",
            window=period,
            unit="index",
            minimum=0.0,
            maximum=100.0,
            compute=_make_rsi(period),
        )
    for period in (14, 20, 60, 252):
        register_feature(
            registry,
            name=f"stochastic_{period}",
            category="momentum",
            description=f"Close location within the {period}-bar range.",
            window=period,
            unit="index",
            minimum=0.0,
            maximum=100.0,
            compute=_make_stochastic(period),
        )
        register_feature(
            registry,
            name=f"distance_from_high_{period}",
            category="momentum",
            description=f"Distance from the {period}-bar closing high.",
            window=period,
            compute=_make_distance(period, high=True),
        )
        register_feature(
            registry,
            name=f"distance_from_low_{period}",
            category="momentum",
            description=f"Distance from the {period}-bar closing low.",
            window=period,
            compute=_make_distance(period, high=False),
        )


def _make_return(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return pct_return(context.closes, period)

    return compute


def _make_rsi(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return rsi(context.closes, period)

    return compute


def _make_stochastic(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _stochastic(context, period)

    return compute


def _make_distance(period: int, *, high: bool) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _distance(context.closes, period, high)

    return compute


def _stochastic(context: FeatureContext, period: int) -> float | None:
    highest = rolling_max(context.highs, period)
    lowest = rolling_min(context.lows, period)
    if highest is None or lowest is None or highest == lowest:
        return None
    return 100.0 * (context.closes[-1] - lowest) / (highest - lowest)


def _distance(values: list[float], period: int, high: bool) -> float | None:
    extreme = rolling_max(values, period) if high else rolling_min(values, period)
    if extreme is None or extreme == 0.0:
        return None
    return values[-1] / extreme - 1.0
