from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from enum import StrEnum


class TradingStyle(StrEnum):
    SCALPING = "scalping"
    DAY_TRADING = "day_trading"
    SWING = "swing"
    POSITION = "position"


class MarketSession(StrEnum):
    CLOSED = "closed"
    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"


@dataclass(frozen=True, slots=True)
class StrategyOperatingProfile:
    style: TradingStyle
    allow_overnight: bool
    allow_weekend: bool
    minimum_holding_period: timedelta = timedelta(0)
    maximum_holding_period: timedelta | None = None
    maximum_trades_per_day: int | None = None
    forced_exit_time: time | None = None
    minimum_liquidity: float = 0.0
    maximum_spread_bps: float | None = None

    def __post_init__(self) -> None:
        if self.maximum_trades_per_day is not None and self.maximum_trades_per_day < 1:
            raise ValueError("maximum_trades_per_day must be positive")
        if self.minimum_liquidity < 0:
            raise ValueError("minimum_liquidity cannot be negative")
        if self.maximum_spread_bps is not None and self.maximum_spread_bps < 0:
            raise ValueError("maximum_spread_bps cannot be negative")
