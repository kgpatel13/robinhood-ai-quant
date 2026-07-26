from __future__ import annotations

import math
from collections.abc import Sequence

from src.atlas.market_models import PriceBar


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def rolling_mean(values: Sequence[float], period: int) -> float | None:
    return None if len(values) < period else mean(values[-period:])


def rolling_std(values: Sequence[float], period: int) -> float | None:
    if len(values) < period or period < 2:
        return None
    selected = values[-period:]
    average = sum(selected) / period
    variance = sum((value - average) ** 2 for value in selected) / (period - 1)
    return math.sqrt(variance)


def ema(values: Sequence[float], period: int) -> float | None:
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    for value in values[period:]:
        result += multiplier * (value - result)
    return result


def pct_return(values: Sequence[float], period: int) -> float | None:
    if len(values) <= period or values[-period - 1] == 0.0:
        return None
    return values[-1] / values[-period - 1] - 1.0


def rolling_min(values: Sequence[float], period: int) -> float | None:
    return None if len(values) < period else min(values[-period:])


def rolling_max(values: Sequence[float], period: int) -> float | None:
    return None if len(values) < period else max(values[-period:])


def true_ranges(bars: Sequence[PriceBar], period: int) -> list[float] | None:
    if len(bars) < period + 1:
        return None
    selected = bars[-(period + 1):]
    values: list[float] = []
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        values.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return values


def atr(bars: Sequence[PriceBar], period: int) -> float | None:
    values = true_ranges(bars, period)
    return None if values is None else sum(values) / period


def rsi(values: Sequence[float], period: int) -> float | None:
    if len(values) < period + 1:
        return None
    changes = [
        current - previous
        for previous, current in zip(values[-period - 1:-1], values[-period:], strict=True)
    ]
    gains = sum(max(change, 0.0) for change in changes) / period
    losses = sum(max(-change, 0.0) for change in changes) / period
    if losses == 0.0:
        return 100.0 if gains > 0.0 else 50.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def log_volatility(values: Sequence[float], period: int) -> float | None:
    if len(values) < period + 1:
        return None
    selected = values[-period - 1:]
    returns: list[float] = []
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        if previous <= 0.0 or current <= 0.0:
            return None
        returns.append(math.log(current / previous))
    std = rolling_std(returns, len(returns))
    return None if std is None else std * math.sqrt(252.0)


def correlation(left: Sequence[float], right: Sequence[float], period: int) -> float | None:
    if len(left) < period or len(right) < period or period < 2:
        return None
    xs = left[-period:]
    ys = right[-period:]
    x_mean = sum(xs) / period
    y_mean = sum(ys) / period
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    x_ss = sum((x - x_mean) ** 2 for x in xs)
    y_ss = sum((y - y_mean) ** 2 for y in ys)
    denominator = math.sqrt(x_ss * y_ss)
    return None if denominator == 0.0 else numerator / denominator
