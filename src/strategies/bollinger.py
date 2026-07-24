from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


@dataclass(frozen=True)
class BollingerMeanReversionStrategy(Strategy):
    plugin_name = "bollinger_mean_reversion"
    period: int = 20
    standard_deviations: float = 2.0

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "Bollinger-band mean reversion",
            self.period + 1,
            "mean_reversion",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("period", (10, 20, 30, 50)),
            StrategyParameter("standard_deviations", (1.5, 2.0, 2.5, 3.0)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"period": 20, "standard_deviations": 2.0}

    def validate_parameters(self) -> None:
        if self.period < 2 or self.standard_deviations <= 0:
            raise ValueError("period must be >= 2 and standard_deviations positive")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        middle = bars["close"].rolling(self.period).mean()
        deviation = bars["close"].rolling(self.period).std(ddof=0)
        lower = middle - self.standard_deviations * deviation
        position = 0.0
        out: list[float] = []
        for close, mid, low in zip(bars["close"], middle, lower, strict=True):
            if pd.notna(low) and close < low:
                position = 1.0
            elif pd.notna(mid) and close >= mid:
                position = 0.0
            out.append(position)
        return pd.Series(out, index=bars.index, dtype=float)
