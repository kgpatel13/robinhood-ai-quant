from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class StrategyAction(StrEnum):
    PROMOTE = "promote"
    CONTINUE = "continue"
    REDUCE = "reduce"
    PAUSE = "pause"


@dataclass(frozen=True)
class StrategyObservation:
    strategy: str
    timestamp: datetime
    equity: float
    realized_pnl: float
    trade_count: int
    expected_slippage_bps: float = 0.0
    realized_slippage_bps: float = 0.0

    @staticmethod
    def now(
        strategy: str,
        equity: float,
        realized_pnl: float,
        trade_count: int,
        expected_slippage_bps: float = 0.0,
        realized_slippage_bps: float = 0.0,
    ) -> StrategyObservation:
        return StrategyObservation(
            strategy,
            datetime.now(UTC),
            equity,
            realized_pnl,
            trade_count,
            expected_slippage_bps,
            realized_slippage_bps,
        )


@dataclass(frozen=True)
class StrategyHealth:
    strategy: str
    score: float
    action: StrategyAction
    total_return: float
    maximum_drawdown: float
    slippage_quality: float
    trade_count: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PaperPortfolioSnapshot:
    as_of: datetime
    strategies: tuple[StrategyHealth, ...]
    champion: str | None
    aggregate_equity: float
