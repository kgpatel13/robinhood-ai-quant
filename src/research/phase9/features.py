from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_last(series: pd.Series) -> float:
    value = series.iloc[-1]
    return float(value) if pd.notna(value) else 0.0


def build_opportunity_features(frame: pd.DataFrame) -> dict[str, float]:
    ordered = frame.sort_values("timestamp").copy()
    close = ordered["adjusted_close"].astype(float)
    high = ordered["high"].astype(float)
    low = ordered["low"].astype(float)
    volume = ordered["volume"].astype(float)
    returns = close.pct_change()

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    momentum_5 = close.pct_change(5)
    momentum_21 = close.pct_change(21)
    volatility_21 = returns.rolling(21).std() * np.sqrt(252.0)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    atr_14 = true_range.rolling(14).mean()
    relative_volume = volume / volume.rolling(20).mean().replace(0, np.nan)
    dollar_volume = close * volume
    drawdown = close / close.cummax() - 1.0
    breakout = close / high.rolling(20).max().shift(1) - 1.0

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    latest_close = _safe_last(close)
    latest_atr = _safe_last(atr_14)
    return {
        "price": latest_close,
        "return_1": _safe_last(returns),
        "momentum_5": _safe_last(momentum_5),
        "momentum_21": _safe_last(momentum_21),
        "trend_fast_slow": _safe_last(ema_fast / ema_slow - 1.0),
        "trend_50_200": _safe_last(sma_50 / sma_200 - 1.0),
        "rsi_14": _safe_last(rsi),
        "annualized_volatility": max(0.0, _safe_last(volatility_21)),
        "atr": max(0.0, latest_atr),
        "atr_percent": latest_atr / latest_close if latest_close > 0 else 0.0,
        "relative_volume": max(0.0, _safe_last(relative_volume)),
        "average_dollar_volume": max(0.0, _safe_last(dollar_volume.rolling(20).mean())),
        "drawdown": min(0.0, _safe_last(drawdown)),
        "breakout_20": _safe_last(breakout),
    }
