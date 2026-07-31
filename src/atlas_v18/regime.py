from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from src.atlas_v18.models import MarketRegime, RegimeSnapshot


class MarketRegimeEngine:
    def __init__(
        self,
        *,
        lookback: int = 20,
        high_volatility: float = 0.55,
        low_volatility: float = 0.12,
        trend_threshold: float = 0.03,
    ) -> None:
        if lookback < 5:
            raise ValueError("lookback must be at least 5")
        self.lookback = lookback
        self.high_volatility = high_volatility
        self.low_volatility = low_volatility
        self.trend_threshold = trend_threshold

    def classify(self, prices: Sequence[float]) -> RegimeSnapshot:
        clean = tuple(float(price) for price in prices if float(price) > 0)
        if len(clean) < self.lookback + 1:
            return RegimeSnapshot(
                regime=MarketRegime.INSUFFICIENT_DATA,
                confidence=0.0,
                trend_return=0.0,
                annualized_volatility=0.0,
                moving_average_gap=0.0,
            )
        window = clean[-(self.lookback + 1) :]
        returns = tuple(window[index] / window[index - 1] - 1.0 for index in range(1, len(window)))
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / max(len(returns) - 1, 1)
        volatility = sqrt(variance) * sqrt(252.0)
        trend_return = window[-1] / window[0] - 1.0
        moving_average = sum(window[:-1]) / (len(window) - 1)
        moving_average_gap = window[-1] / moving_average - 1.0

        if volatility >= self.high_volatility:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(1.0, volatility / max(self.high_volatility, 1e-12) - 0.25)
        elif trend_return >= self.trend_threshold and moving_average_gap > 0:
            regime = MarketRegime.TRENDING_BULL
            confidence = min(1.0, abs(trend_return) / self.trend_threshold)
        elif trend_return <= -self.trend_threshold and moving_average_gap < 0:
            regime = MarketRegime.TRENDING_BEAR
            confidence = min(1.0, abs(trend_return) / self.trend_threshold)
        elif volatility <= self.low_volatility:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = min(1.0, self.low_volatility / max(volatility, 1e-12) - 0.25)
        else:
            regime = MarketRegime.RANGE_BOUND
            confidence = min(1.0, 1.0 - abs(trend_return) / max(self.trend_threshold, 1e-12))

        return RegimeSnapshot(
            regime=regime,
            confidence=max(0.0, confidence),
            trend_return=trend_return,
            annualized_volatility=volatility,
            moving_average_gap=moving_average_gap,
        )
