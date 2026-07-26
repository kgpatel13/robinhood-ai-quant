from __future__ import annotations

from src.atlas.features.calculations import rolling_mean
from src.atlas.features.core import (
    FeatureContext,
    FeatureFunction,
    FeatureRegistry,
    register_feature,
)


def register(registry: FeatureRegistry) -> None:
    for period in (5, 10, 20, 60):
        register_feature(
            registry,
            name=f"relative_volume_{period}d",
            category="volume",
            description=f"Latest volume divided by prior {period}-bar average volume.",
            window=period,
            compute=_make_relative_volume(period),
        )
        register_feature(
            registry,
            name=f"average_dollar_volume_{period}d",
            category="volume",
            description=f"Average close multiplied by volume over {period} bars.",
            window=period,
            unit="currency",
            compute=_make_average_dollar_volume(period),
        )
    register_feature(
        registry,
        name="on_balance_volume",
        category="volume",
        description="Cumulative signed volume based on close direction.",
        unit="volume",
        compute=_obv,
    )
    register_feature(
        registry,
        name="money_flow_ratio_20",
        category="volume",
        description="Positive money flow divided by total absolute money flow over 20 bars.",
        window=20,
        minimum=0.0,
        maximum=1.0,
        compute=_make_money_flow_ratio(20),
    )


def _make_relative_volume(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _relative_volume(context, period)

    return compute


def _make_average_dollar_volume(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _average_dollar_volume(context, period)

    return compute


def _make_money_flow_ratio(period: int) -> FeatureFunction:
    def compute(context: FeatureContext) -> float | None:
        return _money_flow_ratio(context, period)

    return compute


def _relative_volume(context: FeatureContext, period: int) -> float | None:
    if len(context.volumes) < period + 1:
        return None
    baseline = rolling_mean(context.volumes[-period - 1 : -1], period)
    if baseline is None or baseline == 0.0:
        return None
    return context.volumes[-1] / baseline


def _average_dollar_volume(context: FeatureContext, period: int) -> float | None:
    if len(context.bars) < period:
        return None
    return sum(bar.close * bar.volume for bar in context.bars[-period:]) / period


def _obv(context: FeatureContext) -> float | None:
    if len(context.bars) < 2:
        return None
    result = 0.0
    for previous, current in zip(context.bars[:-1], context.bars[1:], strict=True):
        if current.close > previous.close:
            result += current.volume
        elif current.close < previous.close:
            result -= current.volume
    return result


def _money_flow_ratio(context: FeatureContext, period: int) -> float | None:
    if len(context.bars) < period + 1:
        return None
    selected = context.bars[-period - 1 :]
    positive = 0.0
    negative = 0.0
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        typical = (current.high + current.low + current.close) / 3.0
        flow = typical * current.volume
        previous_typical = (previous.high + previous.low + previous.close) / 3.0
        if typical >= previous_typical:
            positive += flow
        else:
            negative += flow
    total = positive + negative
    return None if total == 0.0 else positive / total
