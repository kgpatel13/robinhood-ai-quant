from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.control_center.config import ControlCenterProfile
from src.control_center.models import IntradaySessionState, RankedCandidate
from src.control_center.ranking import IntradayOpportunityRanker, SymbolMetadata
from src.control_center.risk import AllocationDecision, IntradayPortfolioRiskEngine


@dataclass(frozen=True)
class ControlCenterSnapshot:
    as_of: datetime
    profile_name: str
    mode: str
    candidates: tuple[RankedCandidate, ...]
    allocations: tuple[AllocationDecision, ...]
    trades_today: int
    realized_pnl: float
    open_positions: int
    halted: bool


class AtlasControlCenterService:
    def __init__(self, profile: ControlCenterProfile) -> None:
        self.profile = profile
        self.ranker = IntradayOpportunityRanker()
        self.risk = IntradayPortfolioRiskEngine(profile.risk)

    def create_snapshot(
        self,
        bars_by_symbol: Mapping[str, pd.DataFrame],
        state: IntradaySessionState,
        *,
        as_of: datetime,
        metadata: Mapping[str, SymbolMetadata] | None = None,
    ) -> ControlCenterSnapshot:
        candidates = self.ranker.rank(
            bars_by_symbol,
            minimum_score=self.profile.minimum_candidate_score,
            maximum_candidates=self.profile.max_ranked_candidates,
            metadata=metadata,
        )
        allocations = tuple(self.risk.evaluate(item, state, as_of=as_of) for item in candidates)
        return ControlCenterSnapshot(
            as_of=as_of,
            profile_name=self.profile.name,
            mode="PAPER ONLY",
            candidates=candidates,
            allocations=allocations,
            trades_today=state.trades_today,
            realized_pnl=state.realized_pnl,
            open_positions=len(state.positions),
            halted=state.halted,
        )
