from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


@dataclass(frozen=True)
class DonchianBreakoutStrategy(Strategy):
    plugin_name = "donchian_breakout"
    entry_period: int = 55
    exit_period: int = 20

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "Donchian channel breakout",
            self.entry_period + 1,
            "breakout",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("entry_period", (20, 40, 55, 100)),
            StrategyParameter("exit_period", (10, 20, 30, 40)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"entry_period": 55, "exit_period": 20}

    def validate_parameters(self) -> None:
        if self.exit_period < 2 or self.entry_period <= self.exit_period:
            raise ValueError("entry_period must be greater than exit_period >= 2")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        upper = bars["high"].shift(1).rolling(self.entry_period).max()
        lower = bars["low"].shift(1).rolling(self.exit_period).min()
        position = 0.0
        out: list[float] = []
        for close, high_band, low_band in zip(bars["close"], upper, lower, strict=True):
            if pd.notna(high_band) and close > high_band:
                position = 1.0
            elif pd.notna(low_band) and close < low_band:
                position = 0.0
            out.append(position)
        return pd.Series(out, index=bars.index, dtype=float)
