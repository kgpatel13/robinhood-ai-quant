from __future__ import annotations

from src.trading_orchestrator.models import (
    TradeIntentDecision,
    TradeIntentRequest,
    TradeIntentResult,
)


class PaperTradeOrchestrator:
    """Combines research signals and safety gates into a paper-trade intent."""

    _PAUSE_ACTIONS = frozenset({"pause", "rejected", "reject"})
    _REDUCE_ACTIONS = frozenset({"reduce"})
    _REJECT_QUALITY = frozenset({"reject", "rejected"})
    _REDUCE_QUALITY = frozenset({"reduce"})

    def evaluate(self, request: TradeIntentRequest) -> TradeIntentResult:
        reasons: list[str] = []
        portfolio_action = request.portfolio_health_action.strip().lower()
        quality_decision = request.market_quality_decision.strip().lower()

        if abs(request.alpha_score) < request.minimum_alpha_score:
            reasons.append("alpha_score_below_minimum")
        if request.alpha_confidence < request.minimum_alpha_confidence:
            reasons.append("alpha_confidence_below_minimum")
        if not request.regime_approved:
            reasons.append("regime_gate_rejected")
        if quality_decision in self._REJECT_QUALITY:
            reasons.append("market_quality_rejected")
        if portfolio_action in self._PAUSE_ACTIONS:
            reasons.append("strategy_health_paused")

        hard_rejection = any(
            reason
            in {
                "alpha_score_below_minimum",
                "alpha_confidence_below_minimum",
                "regime_gate_rejected",
                "market_quality_rejected",
                "strategy_health_paused",
            }
            for reason in reasons
        )
        side = "buy" if request.alpha_score > 0 else "sell"
        if hard_rejection:
            return TradeIntentResult(
                request.trade_id,
                request.symbol.strip().upper(),
                request.strategy,
                TradeIntentDecision.REJECT,
                0.0,
                side,
                request.alpha_confidence,
                0.0,
                tuple(reasons),
            )

        multiplier = request.regime_size_multiplier * request.market_quality_multiplier
        if quality_decision in self._REDUCE_QUALITY:
            reasons.append("market_quality_reduced")
        if portfolio_action in self._REDUCE_ACTIONS:
            multiplier *= 0.5
            reasons.append("strategy_health_reduced")

        confidence_multiplier = max(0.25, request.alpha_confidence)
        multiplier *= confidence_multiplier
        multiplier = min(1.0, max(0.0, multiplier))
        decision = (
            TradeIntentDecision.APPROVE
            if multiplier >= 0.95 and not reasons
            else TradeIntentDecision.REDUCE
        )
        return TradeIntentResult(
            request.trade_id,
            request.symbol.strip().upper(),
            request.strategy,
            decision,
            request.requested_notional * multiplier,
            side,
            request.alpha_confidence,
            multiplier,
            tuple(reasons),
        )
