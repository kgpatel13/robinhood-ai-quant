from __future__ import annotations

from src.atlas.market_models import MarketRegime


def classify_market_regime(
    *,
    return_20d: float | None,
    volatility_20d: float | None,
    close: float,
    sma_20: float | None,
    sma_50: float | None,
    rsi_14: float | None,
) -> MarketRegime:
    if return_20d is None or volatility_20d is None or sma_20 is None or sma_50 is None:
        return "insufficient_data"

    if return_20d <= -0.20 and volatility_20d >= 0.45:
        return "crash"
    if return_20d >= 0.08 and close > sma_20 > sma_50:
        return "strong_bull"
    if return_20d >= 0.02 and close >= sma_20 and sma_20 >= sma_50:
        return "bull"
    if return_20d <= -0.10 and close < sma_20 < sma_50:
        return "strong_bear"
    if return_20d <= -0.02 and close <= sma_20 and sma_20 <= sma_50:
        return "bear"
    if volatility_20d >= 0.50:
        return "volatile"
    if return_20d > 0.0 and close > sma_20 and (rsi_14 or 50.0) < 60.0:
        return "recovery"
    return "sideways"
