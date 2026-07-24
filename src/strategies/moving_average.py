from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter
from src.strategies.indicators import ema


@dataclass(frozen=True)
class MovingAverageCrossStrategy(Strategy):
    plugin_name = "moving_average_cross"
    fast_period: int = 50
    slow_period: int = 200

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name=self.plugin_name,
            description="Long-only EMA crossover research strategy",
            required_history=self.slow_period,
            category="trend",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("fast_period", (5, 10, 20, 50)),
            StrategyParameter("slow_period", (50, 100, 150, 200)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"fast_period": 50, "slow_period": 200}

    def validate_parameters(self) -> None:
        if self.fast_period < 1:
            raise ValueError("fast_period must be positive")
        if self.slow_period < 2:
            raise ValueError("slow_period must be at least 2")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        fast = ema(bars["close"], self.fast_period)
        slow = ema(bars["close"], self.slow_period)
        return fast.gt(slow).astype(float).fillna(0.0)
