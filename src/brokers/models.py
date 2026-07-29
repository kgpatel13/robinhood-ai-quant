from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.execution.models import utc_now


class BrokerConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class BrokerHealth:
    status: BrokerConnectionStatus
    message: str = ""
    checked_at: datetime = field(default_factory=utc_now)

    @property
    def healthy(self) -> bool:
        return self.status is BrokerConnectionStatus.CONNECTED
