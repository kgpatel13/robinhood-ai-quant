from __future__ import annotations

from datetime import UTC, datetime

from src.brokers.base import BrokerAdapter
from src.robinhood_platform.models import (
    RobinhoodOperationalSnapshot,
    RobinhoodReleaseStage,
)


class RobinhoodOperationsService:
    def __init__(self, adapter: BrokerAdapter) -> None:
        if adapter.name.strip().lower() != "robinhood":
            raise ValueError("RobinhoodOperationsService requires the Robinhood adapter")
        self._adapter = adapter

    def snapshot(
        self,
        stage: RobinhoodReleaseStage,
        *,
        daily_submitted_notional: float = 0.0,
    ) -> RobinhoodOperationalSnapshot:
        health = self._adapter.health_check()
        account = self._adapter.get_account()
        orders = tuple(self._adapter.list_orders())
        reasons: list[str] = []
        if not health.healthy:
            reasons.append(f"broker health is {health.status.value}")
        if stage in {RobinhoodReleaseStage.RESEARCH, RobinhoodReleaseStage.HALTED}:
            reasons.append(f"trading disabled in {stage.value} stage")
        return RobinhoodOperationalSnapshot(
            generated_at=datetime.now(UTC),
            stage=stage,
            account=account,
            orders=orders,
            daily_submitted_notional=daily_submitted_notional,
            trading_allowed=not reasons,
            reasons=tuple(reasons),
        )
