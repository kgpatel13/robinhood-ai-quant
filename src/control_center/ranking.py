from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from src.control_center.models import CandidateStatus, RankedCandidate
from src.strategies.intraday import IntradayMomentumStrategy, IntradaySignal


@dataclass(frozen=True)
class SymbolMetadata:
    sector: str = "Unknown"


class IntradayOpportunityRanker:
    def __init__(self, strategy: IntradayMomentumStrategy | None = None) -> None:
        self.strategy = strategy or IntradayMomentumStrategy()

    def rank(
        self,
        bars_by_symbol: Mapping[str, pd.DataFrame],
        *,
        minimum_score: float,
        maximum_candidates: int,
        metadata: Mapping[str, SymbolMetadata] | None = None,
    ) -> tuple[RankedCandidate, ...]:
        details = metadata or {}
        candidates: list[RankedCandidate] = []
        for symbol, bars in sorted(bars_by_symbol.items()):
            assessment = self.strategy.assess(bars)
            reasons: list[str] = []
            if assessment.signal is not IntradaySignal.LONG:
                reasons.append("strategy signal is flat")
            if assessment.score < minimum_score:
                reasons.append("score below configured minimum")
            status = CandidateStatus.ELIGIBLE if not reasons else CandidateStatus.REJECTED
            candidates.append(
                RankedCandidate(
                    symbol=symbol,
                    strategy="intraday_momentum",
                    score=assessment.score,
                    status=status,
                    suggested_weight=min(0.10, max(0.0, assessment.score * 0.10)),
                    reasons=tuple(reasons),
                    sector=details.get(symbol, SymbolMetadata()).sector,
                )
            )
        candidates.sort(key=lambda item: (-item.score, item.symbol))
        return tuple(candidates[:maximum_candidates])
