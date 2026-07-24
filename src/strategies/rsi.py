from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0.0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass(frozen=True)
class RSIMeanReversionStrategy(Strategy):
    plugin_name = "rsi_mean_reversion"
    period: int = 14
    entry_threshold: float = 30.0
    exit_threshold: float = 55.0

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "Long-only RSI mean reversion",
            self.period + 2,
            "mean_reversion",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return (
            StrategyParameter("period", (7, 14, 21)),
            StrategyParameter("entry_threshold", (20.0, 25.0, 30.0, 35.0)),
            StrategyParameter("exit_threshold", (50.0, 55.0, 60.0, 65.0)),
        )

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"period": 14, "entry_threshold": 30.0, "exit_threshold": 55.0}

    def validate_parameters(self) -> None:
        if self.period < 2:
            raise ValueError("period must be at least 2")
        if not 0 < self.entry_threshold < self.exit_threshold < 100:
            raise ValueError("RSI thresholds must satisfy 0 < entry < exit < 100")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        rsi = _rsi(bars["close"], self.period)
        position = 0.0
        out: list[float] = []
        for value in rsi:
            if pd.notna(value) and value <= self.entry_threshold:
                position = 1.0
            elif pd.notna(value) and value >= self.exit_threshold:
                position = 0.0
            out.append(position)
        return pd.Series(out, index=bars.index, dtype=float)
