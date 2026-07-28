from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class DataFreshnessResult:
    fresh: bool
    age: timedelta
    reason: str


class StaleDataGuard:
    def __init__(self, maximum_age: timedelta) -> None:
        if maximum_age <= timedelta(0):
            raise ValueError("maximum_age must be positive")
        self.maximum_age = maximum_age

    def evaluate(
        self,
        observed_at: datetime,
        *,
        now: datetime | None = None,
    ) -> DataFreshnessResult:
        current = now or datetime.now(UTC)
        age = max(current - observed_at, timedelta(0))
        fresh = age <= self.maximum_age
        return DataFreshnessResult(fresh, age, "fresh" if fresh else "market data is stale")


class PaperKillSwitch:
    def __init__(self) -> None:
        self._engaged = False
        self._reason = ""

    def engage(self, reason: str) -> None:
        self._engaged = True
        self._reason = reason.strip() or "operator request"

    def reset(self) -> None:
        self._engaged = False
        self._reason = ""

    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def reason(self) -> str:
        return self._reason

    def ensure_trading_allowed(self) -> None:
        if self._engaged:
            raise RuntimeError(f"paper trading kill switch engaged: {self._reason}")
