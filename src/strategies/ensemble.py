from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategies.base import Strategy, StrategyMetadata, StrategyParameter


@dataclass(frozen=True)
class EnsembleStrategy(Strategy):
    strategies: tuple[Strategy, ...]
    threshold: float = 0.5
    plugin_name = "ensemble"

    def __post_init__(self) -> None:
        self.validate_parameters()

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            self.plugin_name,
            "Equal-weight strategy ensemble",
            max(strategy.metadata.required_history for strategy in self.strategies),
            "ensemble",
        )

    @classmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        return ()

    @classmethod
    def default_parameters(cls) -> dict[str, int | float]:
        return {"threshold": 0.5}

    def validate_parameters(self) -> None:
        if not self.strategies:
            raise ValueError("ensemble requires at least one strategy")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")

    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        signals = pd.concat(
            [strategy.generate_signals(bars) for strategy in self.strategies], axis=1
        )
        return signals.mean(axis=1).ge(self.threshold).astype(float)
