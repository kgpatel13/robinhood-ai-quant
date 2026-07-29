from __future__ import annotations

from src.regime_intelligence.models import (
    RegimeGateDecision,
    RegimeSnapshot,
    StrategyRegimePolicy,
)


class RegimeStrategyGate:
    def evaluate(
        self, snapshot: RegimeSnapshot, policy: StrategyRegimePolicy
    ) -> RegimeGateDecision:
        if snapshot.regime not in policy.allowed_regimes:
            return RegimeGateDecision(False, 0.0, "strategy_not_allowed_in_current_regime")
        if snapshot.confidence < policy.minimum_confidence:
            return RegimeGateDecision(False, 0.0, "regime_confidence_below_minimum")
        multiplier = min(1.0, max(0.25, snapshot.confidence))
        return RegimeGateDecision(True, multiplier, "regime_policy_approved")
