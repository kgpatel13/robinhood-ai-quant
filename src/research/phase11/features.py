from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.phase10.features import build_feature_frame, classify_regime

FEATURE_COLUMNS = (
    "return_1",
    "momentum_5",
    "momentum_21",
    "trend_fast_slow",
    "trend_50_200",
    "rsi_14",
    "annualized_volatility",
    "atr_percent",
    "relative_volume",
    "drawdown",
    "breakout_20",
    "ema_20_distance",
    "ema_50_distance",
    "sma_20_slope_5",
    "roc_10",
    "macd_histogram",
    "bollinger_width_20",
    "distance_to_20d_high",
    "distance_to_20d_low",
    "volume_change_5",
    "obv_slope_10",
)


def build_phase11_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = build_feature_frame(frame)
    close = result["adjusted_close"].astype(float)
    volume = result["volume"].astype(float)
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()
    sma_20 = close.rolling(20).mean()
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    standard_deviation = close.rolling(20).std()
    price_change = close.diff()
    direction = price_change.gt(0.0).astype(float) - price_change.lt(0.0).astype(float)
    obv = (direction * volume).cumsum()

    result["ema_20_distance"] = close / ema_20 - 1.0
    result["ema_50_distance"] = close / ema_50 - 1.0
    result["sma_20_slope_5"] = sma_20.pct_change(5)
    result["roc_10"] = close.pct_change(10)
    result["macd_histogram"] = (macd - signal) / close
    result["bollinger_width_20"] = 4.0 * standard_deviation / sma_20
    result["distance_to_20d_high"] = close / close.rolling(20).max() - 1.0
    result["distance_to_20d_low"] = close / close.rolling(20).min() - 1.0
    result["volume_change_5"] = volume.pct_change(5)
    result["obv_slope_10"] = obv.diff(10) / volume.rolling(20).mean().replace(0, np.nan)
    result["regime"] = result.apply(_safe_regime, axis=1)
    return result.replace([np.inf, -np.inf], np.nan)


def _safe_regime(row: pd.Series) -> str:
    required = ["price", "market_sma_200", "market_return_63", "annualized_volatility"]
    if row[required].isna().any():
        return "unknown"
    return classify_regime(row)
