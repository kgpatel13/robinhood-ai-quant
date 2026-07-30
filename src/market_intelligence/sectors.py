from __future__ import annotations

from collections.abc import Iterable

from src.market_intelligence.models import SectorObservation, SectorScore


class SectorRotationAnalyzer:
    def rank(self, observations: Iterable[SectorObservation]) -> tuple[SectorScore, ...]:
        rows = tuple(observations)
        if not rows:
            return ()
        scored: list[tuple[SectorObservation, float, float, float]] = []
        for row in rows:
            relative_strength = row.return_1m - row.benchmark_return_1m
            risk_adjusted = (0.6 * row.return_1m + 0.4 * row.return_3m) / max(row.volatility, 0.01)
            score = 0.65 * relative_strength + 0.35 * risk_adjusted
            scored.append((row, score, relative_strength, risk_adjusted))
        scored.sort(key=lambda item: (-item[1], item[0].sector))
        return tuple(
            SectorScore(
                sector=row.sector,
                score=float(score),
                rank=index,
                relative_strength=float(relative_strength),
                risk_adjusted_momentum=float(risk_adjusted),
            )
            for index, (row, score, relative_strength, risk_adjusted) in enumerate(scored, start=1)
        )
