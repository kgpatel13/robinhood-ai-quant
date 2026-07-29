from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class BootstrapConfig:
    simulations: int = 1_000
    confidence_level: float = 0.95
    block_size: int = 1
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.simulations < 100:
            raise ValueError("simulations must be at least 100")
        if not 0.5 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.5 and 1.0")
        if self.block_size < 1:
            raise ValueError("block_size must be positive")


@dataclass(frozen=True)
class RobustnessReport:
    observed_total_return: float
    observed_mean_return: float
    observed_sharpe: float
    total_return_interval: tuple[float, float]
    sharpe_interval: tuple[float, float]
    probability_profitable: float
    probability_positive_sharpe: float
    simulations: int


class TradeReturnBootstrap:
    """Block-bootstrap trade returns to quantify strategy uncertainty."""

    def __init__(self, config: BootstrapConfig | None = None) -> None:
        self.config = config or BootstrapConfig()

    def analyze(self, returns: np.ndarray[Any, Any]) -> RobustnessReport:
        values = np.asarray(returns, dtype=float).reshape(-1)
        if len(values) < 10:
            raise ValueError("at least ten returns are required")
        if not np.isfinite(values).all():
            raise ValueError("returns must be finite")
        rng = np.random.default_rng(self.config.random_state)
        totals = np.empty(self.config.simulations, dtype=float)
        sharpes = np.empty(self.config.simulations, dtype=float)
        for simulation in range(self.config.simulations):
            sample = self._sample(values, rng)
            totals[simulation] = float(np.prod(1.0 + sample) - 1.0)
            sharpes[simulation] = self._sharpe(sample)
        alpha = (1.0 - self.config.confidence_level) / 2.0
        return RobustnessReport(
            observed_total_return=float(np.prod(1.0 + values) - 1.0),
            observed_mean_return=float(values.mean()),
            observed_sharpe=self._sharpe(values),
            total_return_interval=(
                float(np.quantile(totals, alpha)),
                float(np.quantile(totals, 1.0 - alpha)),
            ),
            sharpe_interval=(
                float(np.quantile(sharpes, alpha)),
                float(np.quantile(sharpes, 1.0 - alpha)),
            ),
            probability_profitable=float(np.mean(totals > 0.0)),
            probability_positive_sharpe=float(np.mean(sharpes > 0.0)),
            simulations=self.config.simulations,
        )

    def _sample(
        self, values: np.ndarray[Any, Any], rng: np.random.Generator
    ) -> np.ndarray[Any, Any]:
        if self.config.block_size == 1:
            return rng.choice(values, size=len(values), replace=True)
        blocks_needed = int(np.ceil(len(values) / self.config.block_size))
        starts = rng.integers(0, len(values), size=blocks_needed)
        pieces = [
            np.take(values, np.arange(start, start + self.config.block_size), mode="wrap")
            for start in starts
        ]
        return np.concatenate(pieces)[: len(values)]

    @staticmethod
    def _sharpe(values: np.ndarray[Any, Any]) -> float:
        deviation = float(values.std(ddof=1))
        if deviation == 0.0:
            return 0.0
        return float(values.mean() / deviation * np.sqrt(len(values)))
