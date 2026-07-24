from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import pandas as pd


@dataclass(frozen=True)
class StrategyMetadata:
    name: str
    description: str
    required_history: int
    category: str = "general"
    version: str = "1.0"


@dataclass(frozen=True)
class StrategyParameter:
    name: str
    values: tuple[int | float, ...]
    description: str = ""


class Strategy(ABC):
    plugin_name: ClassVar[str]

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Describe the strategy and its warm-up requirement."""

    @classmethod
    @abstractmethod
    def parameter_space(cls) -> tuple[StrategyParameter, ...]:
        """Return the supported research parameter grid."""

    @classmethod
    @abstractmethod
    def default_parameters(cls) -> dict[str, int | float]:
        """Return conservative default parameters."""

    @abstractmethod
    def validate_parameters(self) -> None:
        """Raise ValueError when configured parameters are invalid."""

    @abstractmethod
    def generate_signals(self, bars: pd.DataFrame) -> pd.Series:
        """Return target exposure in [0, 1] indexed like bars."""
