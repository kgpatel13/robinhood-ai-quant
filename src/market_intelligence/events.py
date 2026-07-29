from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.market_intelligence.models import (
    EventRiskDecision,
    EventSeverity,
    MarketEvent,
)


@dataclass(frozen=True)
class EventRiskPolicy:
    lookahead: timedelta = timedelta(hours=24)
    high_severity_multiplier: float = 0.50
    medium_severity_multiplier: float = 0.75
    block_critical: bool = True
    block_high_for_symbol: bool = False


class EventRiskEngine:
    def __init__(self, policy: EventRiskPolicy | None = None) -> None:
        self.policy = policy or EventRiskPolicy()

    def evaluate(
        self,
        *,
        as_of: datetime,
        symbol: str | None,
        events: Iterable[MarketEvent],
    ) -> EventRiskDecision:
        normalized_symbol = symbol.upper() if symbol else None
        window_end = as_of + self.policy.lookahead
        matching = tuple(
            event
            for event in events
            if event.starts_at <= window_end
            and event.ends_at >= as_of
            and (
                not event.symbols
                or normalized_symbol is None
                or normalized_symbol in {item.upper() for item in event.symbols}
            )
        )
        if not matching:
            return EventRiskDecision(True, 1.0, ("no_material_event_risk",))

        severities = {event.severity for event in matching}
        ids = tuple(sorted(event.event_id for event in matching))
        if EventSeverity.CRITICAL in severities and self.policy.block_critical:
            return EventRiskDecision(False, 0.0, ("critical_event_window",), ids)
        if EventSeverity.HIGH in severities:
            symbol_specific = any(bool(event.symbols) for event in matching)
            if symbol_specific and self.policy.block_high_for_symbol:
                return EventRiskDecision(False, 0.0, ("high_symbol_event_window",), ids)
            return EventRiskDecision(
                True,
                self.policy.high_severity_multiplier,
                ("high_event_risk_reduced_size",),
                ids,
            )
        if EventSeverity.MEDIUM in severities:
            return EventRiskDecision(
                True,
                self.policy.medium_severity_multiplier,
                ("medium_event_risk_reduced_size",),
                ids,
            )
        return EventRiskDecision(True, 1.0, ("low_event_risk",), ids)
