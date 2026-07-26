from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MarketRegime = Literal[
    "strong_bull",
    "bull",
    "sideways",
    "volatile",
    "bear",
    "strong_bear",
    "crash",
    "recovery",
    "insufficient_data",
]


@dataclass(frozen=True)
class PriceBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketFeatures:
    asset_id: str
    symbol: str
    asset_class: str
    timestamp: str
    close: float
    return_1d: float | None
    return_5d: float | None
    return_20d: float | None
    volatility_20d: float | None
    sma_20: float | None
    sma_50: float | None
    ema_20: float | None
    atr_14: float | None
    rsi_14: float | None
    relative_volume_20d: float | None
    distance_from_20d_high: float | None
    trend_strength: float | None
    liquidity_score: float
    data_quality_score: float
    market_quality_score: float
    regime: MarketRegime
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MarketIntelligenceResult:
    platform_version: str
    generated_at_utc: str
    registry_assets: int
    processed_assets: int
    skipped_assets: int
    regime_counts: dict[str, int]
    feature_store_path: str
    market_snapshot_path: str
    errors: dict[str, str]
    complete: bool
