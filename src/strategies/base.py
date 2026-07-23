from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StrategyMetadata:
    name: str
    description: str
    required_history: int


class Strategy(ABC):
    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Describe the strategy and its warm-up requirement."""

    @abstractmethod
    def validate_parameters(self) -> None:
        """Raise ValueError when the configured strategy parameters are invalid."""

    @abstractmethod
    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        """Return target exposure in [0, 1] indexed like bars."""
