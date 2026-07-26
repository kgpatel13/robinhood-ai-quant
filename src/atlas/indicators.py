from __future__ import annotations

import math
from collections.abc import Sequence

from src.atlas.market_models import PriceBar


def simple_moving_average(values: Sequence[float], period: int) -> float | None:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def exponential_moving_average(values: Sequence[float], period: int) -> float | None:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return None
    seed = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    ema = seed
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema


def percentage_return(values: Sequence[float], periods: int) -> float | None:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if len(values) <= periods:
        return None
    previous = values[-(periods + 1)]
    if previous == 0.0:
        return None
    return values[-1] / previous - 1.0


def annualized_volatility(values: Sequence[float], period: int = 20) -> float | None:
    if len(values) < period + 1:
        return None
    returns: list[float] = []
    window = values[-(period + 1) :]
    for previous, current in zip(window[:-1], window[1:], strict=True):
        if previous <= 0.0:
            return None
        returns.append(math.log(current / previous))
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def average_true_range(bars: Sequence[PriceBar], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    true_ranges: list[float] = []
    selected = bars[-(period + 1) :]
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(true_ranges) / period


def relative_strength_index(values: Sequence[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    selected = values[-(period + 1) :]
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        change = current - previous
        if change >= 0.0:
            gains += change
        else:
            losses -= change
    average_gain = gains / period
    average_loss = losses / period
    if average_loss == 0.0:
        return 100.0 if average_gain > 0.0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def relative_volume(volumes: Sequence[float], period: int = 20) -> float | None:
    if len(volumes) < period + 1:
        return None
    baseline = sum(volumes[-(period + 1) : -1]) / period
    if baseline <= 0.0:
        return None
    return volumes[-1] / baseline


def distance_from_high(values: Sequence[float], period: int = 20) -> float | None:
    if len(values) < period:
        return None
    highest = max(values[-period:])
    if highest <= 0.0:
        return None
    return values[-1] / highest - 1.0
