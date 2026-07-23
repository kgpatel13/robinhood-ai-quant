from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata
from src.strategies.indicators import ema


@dataclass(frozen=True)
class MovingAverageCrossStrategy(Strategy):
    fast_period: int = 50
    slow_period: int = 200

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="moving_average_cross",
            description="Long-only EMA crossover research strategy",
            required_history=self.slow_period,
        )

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        fast = ema(bars["close"], self.fast_period)
        slow = ema(bars["close"], self.slow_period)
        return fast.gt(slow).astype(float).fillna(0.0)
