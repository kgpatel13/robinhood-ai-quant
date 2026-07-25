from __future__ import annotations

import numpy as np
import pandas as pd


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values("timestamp").copy().reset_index(drop=True)
    close = ordered["adjusted_close"].astype(float)
    high = ordered["high"].astype(float)
    low = ordered["low"].astype(float)
    volume = ordered["volume"].astype(float)
    returns = close.pct_change()

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)

    base_columns = [
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
    ]
    result = ordered[base_columns].copy()
    result["price"] = close
    result["return_1"] = returns
    result["momentum_5"] = close.pct_change(5)
    result["momentum_21"] = close.pct_change(21)
    result["trend_fast_slow"] = ema_fast / ema_slow - 1.0
    result["trend_50_200"] = sma_50 / sma_200 - 1.0
    result["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
    result["annualized_volatility"] = returns.rolling(21).std() * np.sqrt(252.0)
    result["atr"] = true_range.rolling(14).mean()
    result["atr_percent"] = result["atr"] / close
    result["relative_volume"] = volume / volume.rolling(20).mean().replace(0, np.nan)
    result["average_dollar_volume"] = (close * volume).rolling(20).mean()
    result["drawdown"] = close / close.cummax() - 1.0
    result["breakout_20"] = close / high.rolling(20).max().shift(1) - 1.0
    result["market_sma_200"] = sma_200
    result["market_return_63"] = close.pct_change(63)
    return result.replace([np.inf, -np.inf], np.nan)


def classify_regime(row: pd.Series) -> str:
    price = float(row["price"])
    sma_200 = float(row["market_sma_200"])
    return_63 = float(row["market_return_63"])
    volatility = float(row["annualized_volatility"])
    if volatility >= 0.75:
        return "high_volatility"
    if price >= sma_200 and return_63 >= 0.03:
        return "bull"
    if price < sma_200 and return_63 <= -0.03:
        return "bear"
    return "sideways"
