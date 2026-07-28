from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

import pandas as pd

from src.execution.calendar import MarketSession
from src.strategies.intraday import IntradayMomentumStrategy, IntradaySignal


class IntradayAction(StrEnum):
    HOLD = "hold"
    ENTER = "enter"
    EXIT = "exit"
    FLATTEN = "flatten"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class IntradayPaperDecision:
    symbol: str
    action: IntradayAction
    score: float
    reason: str


type IntradayBarsProvider = Callable[[datetime], Mapping[str, pd.DataFrame]]


class IntradayPaperOrchestrator:
    """Create paper-only decisions; this class has no broker submission capability."""

    def __init__(
        self,
        bars_provider: IntradayBarsProvider,
        strategy: IntradayMomentumStrategy | None = None,
        *,
        market_session: MarketSession | None = None,
        liquidation_time: time = time(15, 55),
    ) -> None:
        self.bars_provider = bars_provider
        self.strategy = strategy or IntradayMomentumStrategy()
        self.market_session = market_session or MarketSession()
        self.liquidation_time = liquidation_time

    def evaluate(
        self,
        as_of: datetime,
        open_positions: frozenset[str] = frozenset(),
    ) -> tuple[IntradayPaperDecision, ...]:
        local = as_of.astimezone(ZoneInfo(self.market_session.timezone))
        if not self.market_session.is_trading_day(local.date()):
            return (IntradayPaperDecision("*", IntradayAction.BLOCKED, 0.0, "non-trading-day"),)
        if local.time() >= self.liquidation_time:
            return tuple(
                IntradayPaperDecision(symbol, IntradayAction.FLATTEN, 0.0, "end-of-day")
                for symbol in sorted(open_positions)
            )
        if not self.market_session.is_open(as_of):
            return (IntradayPaperDecision("*", IntradayAction.BLOCKED, 0.0, "market-closed"),)
        decisions = []
        for symbol, bars in sorted(self.bars_provider(as_of).items()):
            assessment = self.strategy.assess(bars)
            held = symbol in open_positions
            if held and assessment.signal is IntradaySignal.FLAT:
                action = IntradayAction.EXIT
            elif not held and assessment.signal is IntradaySignal.LONG:
                action = IntradayAction.ENTER
            else:
                action = IntradayAction.HOLD
            decisions.append(
                IntradayPaperDecision(symbol, action, assessment.score, assessment.signal.value)
            )
        return tuple(decisions)
