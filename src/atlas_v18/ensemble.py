from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.atlas_v18.models import (
    EnsembleDecision,
    MarketRegime,
    SignalAction,
    StrategySignal,
)


class StrategyVotingEngine:
    def __init__(self, *, decision_threshold: float = 0.15) -> None:
        if not 0 <= decision_threshold <= 1:
            raise ValueError("decision_threshold must be between zero and one")
        self.decision_threshold = decision_threshold

    def decide(
        self,
        signals: Sequence[StrategySignal],
        *,
        regime: MarketRegime,
        strategy_weights: Mapping[str, float] | None = None,
    ) -> EnsembleDecision:
        weights = strategy_weights or {}
        scores = {action: 0.0 for action in SignalAction}
        contributors: list[str] = []
        total_weight = 0.0

        for signal in signals:
            base_weight = max(0.0, float(weights.get(signal.strategy, 1.0)))
            affinity = (
                1.0 if not signal.regime_affinity or regime in signal.regime_affinity else 0.35
            )
            effective = base_weight * affinity * min(1.0, max(0.0, signal.confidence))
            scores[signal.action] += effective
            total_weight += effective
            if effective > 0:
                contributors.append(signal.strategy)

        if total_weight <= 1e-12:
            return EnsembleDecision(
                action=SignalAction.WAIT,
                confidence=0.0,
                weighted_buy=0.0,
                weighted_sell=0.0,
                weighted_wait=1.0,
                contributors=(),
                rationale="No eligible strategy votes.",
            )

        normalized = {action: score / total_weight for action, score in scores.items()}
        directional_edge = abs(normalized[SignalAction.BUY] - normalized[SignalAction.SELL])
        if directional_edge < self.decision_threshold:
            action = SignalAction.WAIT
        elif normalized[SignalAction.BUY] > normalized[SignalAction.SELL]:
            action = SignalAction.BUY
        else:
            action = SignalAction.SELL
        confidence = (
            normalized[action] if action is not SignalAction.WAIT else 1.0 - directional_edge
        )
        return EnsembleDecision(
            action=action,
            confidence=min(1.0, max(0.0, confidence)),
            weighted_buy=normalized[SignalAction.BUY],
            weighted_sell=normalized[SignalAction.SELL],
            weighted_wait=normalized[SignalAction.WAIT],
            contributors=tuple(contributors),
            rationale=(
                f"{action.value.upper()} selected with {confidence:.1%} confidence "
                f"under {regime.value}."
            ),
        )
