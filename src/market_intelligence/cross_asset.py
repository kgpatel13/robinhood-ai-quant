from __future__ import annotations

from dataclasses import dataclass

from src.market_intelligence.models import (
    CrossAssetAssessment,
    CrossAssetSnapshot,
    MarketState,
)


@dataclass(frozen=True)
class CrossAssetPolicy:
    risk_on_threshold: float = 0.20
    risk_off_threshold: float = -0.20
    stress_threshold: float = -0.55


class CrossAssetAnalyzer:
    def __init__(self, policy: CrossAssetPolicy | None = None) -> None:
        self.policy = policy or CrossAssetPolicy()

    def assess(self, snapshot: CrossAssetSnapshot) -> CrossAssetAssessment:
        contributions = {
            "equity": 0.35 * self._bounded(snapshot.equity_return * 20.0),
            "bonds": 0.15 * self._bounded(snapshot.bond_return * 25.0),
            "dollar": -0.15 * self._bounded(snapshot.dollar_return * 30.0),
            "volatility": -0.25 * self._bounded(snapshot.volatility_return * 10.0),
            "credit": 0.07 * self._bounded(snapshot.credit_return * 25.0),
            "commodities": 0.03 * self._bounded(snapshot.commodity_return * 20.0),
        }
        score = float(sum(contributions.values()))
        state = self._state(score)
        confidence = min(0.99, 0.50 + min(abs(score), 1.0) * 0.45)
        reasons = tuple(
            name
            for name, value in sorted(
                contributions.items(), key=lambda item: abs(item[1]), reverse=True
            )
            if abs(value) >= 0.03
        )
        return CrossAssetAssessment(state, score, confidence, contributions, reasons)

    def _state(self, score: float) -> MarketState:
        if score <= self.policy.stress_threshold:
            return MarketState.STRESS
        if score <= self.policy.risk_off_threshold:
            return MarketState.RISK_OFF
        if score >= self.policy.risk_on_threshold:
            return MarketState.RISK_ON
        return MarketState.NEUTRAL

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(-1.0, value))
