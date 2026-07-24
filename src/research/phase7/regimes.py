from __future__ import annotations

import pandas as pd


def classify_regimes(bars: pd.DataFrame, lookback: int = 63) -> pd.Series:
    close = bars["close"].astype(float)
    returns = close.pct_change().fillna(0.0)
    trend = close / close.shift(lookback) - 1.0
    volatility = returns.rolling(lookback).std(ddof=0) * (252.0**0.5)
    median_vol = float(volatility.median()) if volatility.notna().any() else 0.0
    labels = pd.Series("sideways", index=bars.index, dtype="object")
    labels[trend > 0.10] = "bull"
    labels[trend < -0.10] = "bear"
    labels[(volatility > median_vol) & (trend.abs() <= 0.10)] = "high_volatility"
    labels[(volatility <= median_vol) & (trend.abs() <= 0.10)] = "low_volatility"
    return labels


def regime_score_from_windows(window_frame: pd.DataFrame) -> float:
    if window_frame.empty or "total_return" not in window_frame:
        return 0.0
    values = window_frame["total_return"].astype(float)
    return float((values > 0.0).mean())
