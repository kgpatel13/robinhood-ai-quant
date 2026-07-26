from __future__ import annotations

from src.atlas.features.calculations import ema, pct_return, rolling_mean
from src.atlas.features.core import (
    FeatureContext,
    FeatureFunction,
    FeatureRegistry,
    register_feature,
)


def register(registry: FeatureRegistry) -> None:
    for period in (5, 10, 20, 50, 100, 200):
        register_feature(
            registry,
            name=f"sma_{period}",
            category="trend",
            description=f"Simple moving average over {period} bars.",
            window=period,
            unit="price",
            compute=_make_sma(period),
        )
    for period in (5, 10, 20, 50, 100, 200):
        register_feature(
            registry,
            name=f"ema_{period}",
            category="trend",
            description=f"Exponential moving average over {period} bars.",
            window=period,
            unit="price",
            compute=_make_ema(period),
        )
    for period in (20, 50, 100, 200):
        register_feature(
            registry,
            name=f"price_to_sma_{period}",
            category="trend",
            description=f"Latest close relative to the {period}-bar SMA.",
            window=period,
            compute=_make_price_to_average(period, use_ema=False),
        )
    register_feature(
        registry,
        name="macd_12_26",
        category="trend",
        description="Difference between the 12-bar and 26-bar EMA.",
        window=26,
        unit="price",
        compute=_macd,
    )
    register_feature(
        registry,
        name="trend_persistence_20",
        category="trend",
        description="Fraction of positive daily returns in the last 20 bars.",
        window=20,
        minimum=0.0,
        maximum=1.0,
        compute=_make_persistence(20),
    )
    register_feature(
        registry,
        name="trend_persistence_60",
        category="trend",
        description="Fraction of positive daily returns in the last 60 bars.",
        window=60,
        minimum=0.0,
        maximum=1.0,
        compute=_make_persistence(60),
    )


def _make_sma(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return rolling_mean(context.closes, period)

    return compute


def _make_ema(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return ema(context.closes, period)

    return compute


def _make_price_to_average(period: int, *, use_ema: bool) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _price_to_average(context, period, use_ema)

    return compute


def _make_persistence(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _persistence(context, period)

    return compute


def _price_to_average(context: FeatureContext, period: int, use_ema: bool) -> float | None:
    average = ema(context.closes, period) if use_ema else rolling_mean(context.closes, period)
    if average is None or average == 0.0:
        return None
    return context.closes[-1] / average - 1.0


def _macd(context: FeatureContext) -> float | None:
    fast = ema(context.closes, 12)
    slow = ema(context.closes, 26)
    return None if fast is None or slow is None else fast - slow


def _persistence(context: FeatureContext, period: int) -> float | None:
    if len(context.closes) < period + 1:
        return None
    values = [
        pct_return(context.closes[: index + 1], 1)
        for index in range(len(context.closes) - period, len(context.closes))
    ]
    present = [value for value in values if value is not None]
    return None if not present else sum(value > 0.0 for value in present) / len(present)
