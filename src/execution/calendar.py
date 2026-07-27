from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketSession:
    market_open: time = time(9, 30)
    market_close: time = time(16, 0)
    timezone: str = "America/New_York"
    holidays: frozenset[date] = frozenset()

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays

    def is_open(self, moment: datetime) -> bool:
        local = moment.astimezone(ZoneInfo(self.timezone))
        return (
            self.is_trading_day(local.date())
            and self.market_open <= local.time() < self.market_close
        )
