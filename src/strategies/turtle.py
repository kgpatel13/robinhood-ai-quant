from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


@dataclass(frozen=True)
class TurtleTradingStrategy(Strategy):
    plugin_name = "turtle_trading"
    entry_period: int = 55
    exit_period: int = 20
    trend_period: int = 200

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "Donchian breakout with trend filter",
            max(self.entry_period, self.trend_period) + 1,
            "trend",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("entry_period", (20, 55, 100)),
            StrategyParameter("exit_period", (10, 20, 40)),
            StrategyParameter("trend_period", (100, 150, 200)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"entry_period": 55, "exit_period": 20, "trend_period": 200}

    def validate_parameters(self) -> None:
        if self.exit_period < 2 or self.entry_period <= self.exit_period:
            raise ValueError("entry_period must be greater than exit_period >= 2")
        if self.trend_period < self.entry_period:
            raise ValueError("trend_period must be at least entry_period")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        upper = bars["high"].shift(1).rolling(self.entry_period).max()
        lower = bars["low"].shift(1).rolling(self.exit_period).min()
        trend = bars["close"].rolling(self.trend_period).mean()
        position = 0.0
        out: list[float] = []
        for close, hi, lo, ma in zip(bars["close"], upper, lower, trend, strict=True):
            if pd.notna(hi) and pd.notna(ma) and close > hi and close > ma:
                position = 1.0
            elif pd.notna(lo) and close < lo:
                position = 0.0
            out.append(position)
        return pd.Series(out, index=bars.index, dtype=float)
