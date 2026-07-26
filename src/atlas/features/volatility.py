from __future__ import annotations

from src.atlas.features.calculations import atr, log_volatility, rolling_mean, rolling_std
from src.atlas.features.core import (
    FeatureContext,
    FeatureFunction,
    FeatureRegistry,
    register_feature,
)


def register(registry: FeatureRegistry) -> None:
    for period in (5, 10, 20, 60, 120):
        register_feature(
            registry,
            name=f"volatility_{period}d",
            category="volatility",
            description=f"Annualized close-to-close volatility over {period} bars.",
            window=period,
            unit="annualized_ratio",
            compute=_make_log_volatility(period),
        )
    for period in (7, 14, 20, 50):
        register_feature(
            registry,
            name=f"atr_{period}",
            category="volatility",
            description=f"Average true range over {period} bars.",
            window=period,
            unit="price",
            compute=_make_atr(period),
        )
        register_feature(
            registry,
            name=f"atr_pct_{period}",
            category="volatility",
            description=f"Average true range divided by latest close over {period} bars.",
            window=period,
            compute=_make_atr_pct(period),
        )
    for period in (20, 50):
        register_feature(
            registry,
            name=f"bollinger_z_{period}",
            category="volatility",
            description=f"Standardized distance from the {period}-bar moving average.",
            window=period,
            unit="zscore",
            compute=_make_bollinger_z(period),
        )
        register_feature(
            registry,
            name=f"bollinger_width_{period}",
            category="volatility",
            description=f"Four standard deviations divided by the {period}-bar average.",
            window=period,
            compute=_make_bollinger_width(period),
        )


def _make_log_volatility(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return log_volatility(context.closes, period)

    return compute


def _make_atr(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return atr(context.bars, period)

    return compute


def _make_atr_pct(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _atr_pct(context, period)

    return compute


def _make_bollinger_z(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _bollinger_z(context, period)

    return compute


def _make_bollinger_width(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _bollinger_width(context, period)

    return compute


def _atr_pct(context: FeatureContext, period: int) -> float | None:
    value = atr(context.bars, period)
    close = context.closes[-1]
    return None if value is None or close == 0.0 else value / close


def _bollinger_z(context: FeatureContext, period: int) -> float | None:
    average = rolling_mean(context.closes, period)
    deviation = rolling_std(context.closes, period)
    if average is None or deviation is None or deviation == 0.0:
        return None
    return (context.closes[-1] - average) / deviation


def _bollinger_width(context: FeatureContext, period: int) -> float | None:
    average = rolling_mean(context.closes, period)
    deviation = rolling_std(context.closes, period)
    if average is None or average == 0.0 or deviation is None:
        return None
    return 4.0 * deviation / average
