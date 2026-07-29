from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureMetadata:
    name: str
    version: str
    description: str = ""

    @property
    def identifier(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True)
class FeatureBuildConfig:
    price_column: str = "close"
    high_column: str = "high"
    low_column: str = "low"
    volume_column: str = "volume"
    return_windows: tuple[int, ...] = (1, 5, 20)
    volatility_window: int = 20
    momentum_window: int = 20
    rsi_window: int = 14
