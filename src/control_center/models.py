from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class CandidateStatus(StrEnum):
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    COOLDOWN = "cooldown"


@dataclass(frozen=True)
class RankedCandidate:
    symbol: str
    strategy: str
    score: float
    status: CandidateStatus
    suggested_weight: float
    reasons: tuple[str, ...] = ()
    sector: str = "Unknown"


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    strategy: str
    sector: str = "Unknown"
    opened_at: datetime | None = None

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.current_price - self.entry_price)


@dataclass
class IntradaySessionState:
    session_date: str
    starting_equity: float
    realized_pnl: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0
    halted: bool = False
    halt_reason: str = ""
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    cooldown_until: dict[str, datetime] = field(default_factory=dict)
    processed_decision_ids: set[str] = field(default_factory=set)
