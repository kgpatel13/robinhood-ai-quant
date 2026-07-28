from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class IntradaySignal(StrEnum):
    LONG = "long"
    FLAT = "flat"


@dataclass(frozen=True)
class IntradayStrategyConfig:
    fast_window: int = 5
    slow_window: int = 15
    volume_window: int = 20
    minimum_relative_volume: float = 0.8
    minimum_momentum: float = 0.001

    def __post_init__(self) -> None:
        if self.fast_window < 2 or self.slow_window <= self.fast_window:
            raise ValueError("slow_window must be greater than fast_window")
        if self.volume_window < 2:
            raise ValueError("volume_window must be at least two")


@dataclass(frozen=True)
class IntradayAssessment:
    signal: IntradaySignal
    score: float
    momentum: float
    trend_strength: float
    relative_volume: float
    volatility: float


class IntradayMomentumStrategy:
    def __init__(self, config: IntradayStrategyConfig | None = None) -> None:
        self.config = config or IntradayStrategyConfig()

    def assess(self, bars: pd.DataFrame) -> IntradayAssessment:
        required = max(self.config.slow_window, self.config.volume_window) + 1
        if len(bars) < required:
            return IntradayAssessment(IntradaySignal.FLAT, 0.0, 0.0, 0.0, 0.0, 0.0)
        close = bars["close"].astype(float)
        volume = bars["volume"].astype(float)
        fast = float(close.rolling(self.config.fast_window).mean().iloc[-1])
        slow = float(close.rolling(self.config.slow_window).mean().iloc[-1])
        momentum = float(close.iloc[-1] / close.iloc[-self.config.fast_window] - 1)
        trend = max(-1.0, min(1.0, (fast / slow - 1) * 100)) if slow else 0.0
        average_volume = float(volume.iloc[-self.config.volume_window : -1].mean())
        relative_volume = float(volume.iloc[-1] / average_volume) if average_volume > 0 else 0.0
        volatility = float(close.pct_change().iloc[-self.config.slow_window :].std(ddof=0))
        score = max(
            0.0, min(1.0, 0.45 + trend * 0.25 + momentum * 20 + (relative_volume - 1) * 0.1)
        )
        long_signal = (
            fast > slow
            and momentum >= self.config.minimum_momentum
            and relative_volume >= self.config.minimum_relative_volume
        )
        return IntradayAssessment(
            signal=IntradaySignal.LONG if long_signal else IntradaySignal.FLAT,
            score=score if long_signal else 0.0,
            momentum=momentum,
            trend_strength=trend,
            relative_volume=relative_volume,
            volatility=volatility,
        )
