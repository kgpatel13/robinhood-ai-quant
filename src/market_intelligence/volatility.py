from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.market_intelligence.models import VolatilityAssessment


@dataclass(frozen=True)
class VolatilityPolicy:
    window: int = 20
    history_window: int = 252
    elevated_percentile: float = 0.80
    expansion_threshold: float = 1.30
    ewma_decay: float = 0.94


class VolatilityForecaster:
    def __init__(self, policy: VolatilityPolicy | None = None) -> None:
        self.policy = policy or VolatilityPolicy()

    def assess(self, returns: pd.Series) -> VolatilityAssessment:
        clean = pd.to_numeric(returns, errors="coerce").dropna().astype(float)
        minimum = self.policy.window * 2
        if len(clean) < minimum:
            raise ValueError(f"at least {minimum} returns are required")
        rolling = clean.rolling(self.policy.window).std(ddof=0) * math.sqrt(252)
        valid = rolling.dropna().tail(self.policy.history_window)
        current = float(valid.iloc[-1])
        previous = float(valid.iloc[-self.policy.window])
        expansion = current / previous if previous > 0 else 1.0
        percentile = float((valid <= current).mean())
        variance = self._ewma_variance(clean.tail(self.policy.history_window))
        forecast = math.sqrt(max(variance, 0.0) * 252)
        elevated = (
            percentile >= self.policy.elevated_percentile
            or expansion >= self.policy.expansion_threshold
        )
        return VolatilityAssessment(current, percentile, expansion, forecast, elevated)

    def _ewma_variance(self, returns: pd.Series) -> float:
        decay = self.policy.ewma_decay
        variance = float(returns.iloc[0] ** 2)
        for value in returns.iloc[1:]:
            variance = decay * variance + (1.0 - decay) * float(value**2)
        return variance
