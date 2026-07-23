from __future__ import annotations

import pandas as pd


def sma(values: pd.Series, period: int) -> pd.Series:
    _validate_period(period)
    return values.rolling(period, min_periods=period).mean()


def ema(values: pd.Series, period: int) -> pd.Series:
    _validate_period(period)
    return values.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(values: pd.Series, period: int = 14) -> pd.Series:
    _validate_period(period)
    delta = values.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    average_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0.0, float("nan"))
    result = 100.0 - (100.0 / (1.0 + relative_strength))
    return result.fillna(100.0).where(average_gain.ne(0.0), 0.0)


def true_range(bars: pd.DataFrame) -> pd.Series:
    previous_close = bars["close"].shift(1)
    ranges = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - previous_close).abs(),
            (bars["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    _validate_period(period)
    return true_range(bars).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def macd(
    values: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> pd.DataFrame:
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    line = fast - slow
    signal = line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
    return pd.DataFrame({"macd": line, "signal": signal, "histogram": line - signal})


def bollinger_bands(
    values: pd.Series, period: int = 20, standard_deviations: float = 2.0
) -> pd.DataFrame:
    _validate_period(period)
    middle = sma(values, period)
    deviation = values.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame(
        {
            "lower": middle - standard_deviations * deviation,
            "middle": middle,
            "upper": middle + standard_deviations * deviation,
        }
    )


def vwap(bars: pd.DataFrame) -> pd.Series:
    typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    cumulative_volume = bars["volume"].cumsum().replace(0.0, float("nan"))
    return (typical_price * bars["volume"]).cumsum() / cumulative_volume


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be positive")
