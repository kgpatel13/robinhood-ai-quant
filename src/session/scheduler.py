from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class ScheduledJob:
    name: str
    interval: timedelta
    callback: Callable[[], None]
    next_run: datetime
    catch_up: bool = True


class RuntimeScheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}

    def add_interval_job(
        self,
        name: str,
        interval: timedelta,
        callback: Callable[[], None],
        *,
        start_at: datetime | None = None,
        catch_up: bool = True,
    ) -> None:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        if name in self._jobs:
            raise ValueError(f"job already exists: {name}")
        self._jobs[name] = ScheduledJob(
            name,
            interval,
            callback,
            start_at or datetime.now(UTC),
            catch_up,
        )

    def run_due(self, now: datetime | None = None) -> tuple[str, ...]:
        current = now or datetime.now(UTC)
        executed: list[str] = []
        for job in sorted(self._jobs.values(), key=lambda item: item.next_run):
            if job.next_run > current:
                continue
            job.callback()
            executed.append(job.name)
            if job.catch_up:
                while job.next_run <= current:
                    job.next_run += job.interval
            else:
                job.next_run = current + job.interval
        return tuple(executed)

    def snapshot(self) -> dict[str, str]:
        return {name: job.next_run.isoformat() for name, job in self._jobs.items()}
