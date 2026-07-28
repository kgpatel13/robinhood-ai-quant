from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from src.session.models import MarketSession, StrategyOperatingProfile

ET = ZoneInfo("America/New_York")


class USMarketCalendar:
    """Dependency-free US equity session classifier with configurable closures."""

    def __init__(
        self,
        *,
        holidays: set[date] | None = None,
        half_days: set[date] | None = None,
    ) -> None:
        self._holidays = holidays or set()
        self._half_days = half_days or set()

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self._holidays

    def regular_close(self, day: date) -> time:
        return time(13, 0) if day in self._half_days else time(16, 0)

    def session_at(self, moment: datetime) -> MarketSession:
        local = moment.astimezone(ET)
        if not self.is_trading_day(local.date()):
            return MarketSession.CLOSED
        current = local.time().replace(tzinfo=None)
        if time(4, 0) <= current < time(9, 30):
            return MarketSession.PREMARKET
        if time(9, 30) <= current < self.regular_close(local.date()):
            return MarketSession.REGULAR
        if self.regular_close(local.date()) <= current < time(20, 0):
            return MarketSession.AFTER_HOURS
        return MarketSession.CLOSED

    def entry_allowed(self, profile: StrategyOperatingProfile, moment: datetime) -> bool:
        local = moment.astimezone(ET)
        if not self.is_trading_day(local.date()) and not profile.allow_weekend:
            return False
        return self.session_at(moment) is MarketSession.REGULAR

    def force_exit_due(self, profile: StrategyOperatingProfile, moment: datetime) -> bool:
        if profile.allow_overnight or profile.forced_exit_time is None:
            return False
        local_time = moment.astimezone(ET).time().replace(tzinfo=None)
        return local_time >= profile.forced_exit_time
