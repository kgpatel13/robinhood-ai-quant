from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    status: HealthStatus
    checked_at: datetime
    message: str = ""


class HealthMonitor:
    def __init__(self, *, heartbeat_timeout: timedelta = timedelta(minutes=2)) -> None:
        self._timeout = heartbeat_timeout
        self._heartbeats: dict[str, datetime] = {}
        self._explicit: dict[str, ComponentHealth] = {}

    def heartbeat(self, component: str, *, at: datetime | None = None) -> None:
        self._heartbeats[component] = at or datetime.now(UTC)

    def report(self, health: ComponentHealth) -> None:
        self._explicit[health.name] = health

    def snapshot(self, *, now: datetime | None = None) -> tuple[ComponentHealth, ...]:
        current = now or datetime.now(UTC)
        output = dict(self._explicit)
        for name, heartbeat in self._heartbeats.items():
            age = current - heartbeat
            status = HealthStatus.HEALTHY if age <= self._timeout else HealthStatus.UNHEALTHY
            output[name] = ComponentHealth(name, status, current, f"heartbeat age={age}")
        return tuple(sorted(output.values(), key=lambda item: item.name))

    def overall_status(self, *, now: datetime | None = None) -> HealthStatus:
        statuses = {item.status for item in self.snapshot(now=now)}
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
