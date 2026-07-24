from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


@dataclass(frozen=True)
class ATRBreakoutStrategy(Strategy):
    plugin_name = "atr_breakout"
    lookback: int = 20
    atr_period: int = 14
    atr_multiple: float = 1.0

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "ATR-filtered price breakout",
            max(self.lookback, self.atr_period) + 2,
            "breakout",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("lookback", (10, 20, 40, 60)),
            StrategyParameter("atr_period", (7, 14, 21)),
            StrategyParameter("atr_multiple", (0.5, 1.0, 1.5, 2.0)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"lookback": 20, "atr_period": 14, "atr_multiple": 1.0}

    def validate_parameters(self) -> None:
        if self.lookback < 2 or self.atr_period < 2 or self.atr_multiple <= 0:
            raise ValueError("lookback/atr_period must be >= 2 and atr_multiple positive")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        previous_close = bars["close"].shift(1)
        true_range = pd.concat(
            [
                bars["high"] - bars["low"],
                (bars["high"] - previous_close).abs(),
                (bars["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(self.atr_period).mean()
        baseline = bars["close"].shift(1).rolling(self.lookback).max()
        entry = baseline + self.atr_multiple * atr
        exit_line = bars["close"].shift(1).rolling(self.lookback).mean()
        position = 0.0
        out: list[float] = []
        for close, high_line, low_line in zip(bars["close"], entry, exit_line, strict=True):
            if pd.notna(high_line) and close > high_line:
                position = 1.0
            elif pd.notna(low_line) and close < low_line:
                position = 0.0
            out.append(position)
        return pd.Series(out, index=bars.index, dtype=float)
