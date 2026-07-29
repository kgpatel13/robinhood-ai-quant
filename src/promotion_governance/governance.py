from __future__ import annotations

from src.promotion_governance.models import (
    PromotionDecision,
    PromotionEvidence,
    PromotionPolicy,
    PromotionReview,
)


class StrategyPromotionGovernor:
    """Applies deterministic, auditable promotion and demotion rules."""

    _STAGE_ORDER = ("research", "shadow", "paper", "live_candidate")

    def __init__(self, policy: PromotionPolicy | None = None) -> None:
        self.policy = policy or PromotionPolicy()

    def review(self, evidence: PromotionEvidence) -> PromotionReview:
        stage = evidence.current_stage.strip().lower()
        if stage not in self._STAGE_ORDER:
            raise ValueError(f"unsupported stage: {evidence.current_stage}")
        if evidence.hard_risk_breach:
            return PromotionReview(
                evidence.strategy,
                PromotionDecision.REJECT,
                "research",
                False,
                ("hard_risk_breach",),
            )

        reasons = self._eligibility_reasons(evidence)
        if reasons:
            severe = (
                evidence.health_score < self.policy.minimum_health_score * 0.65
                or evidence.maximum_drawdown > self.policy.maximum_drawdown * 1.5
            )
            if severe and stage != "research":
                target_index = max(0, self._STAGE_ORDER.index(stage) - 1)
                return PromotionReview(
                    evidence.strategy,
                    PromotionDecision.DEMOTE,
                    self._STAGE_ORDER[target_index],
                    False,
                    tuple(reasons),
                )
            return PromotionReview(
                evidence.strategy,
                PromotionDecision.HOLD,
                stage,
                False,
                tuple(reasons),
            )

        if stage == "research":
            return PromotionReview(
                evidence.strategy,
                PromotionDecision.PROMOTE_TO_SHADOW,
                "shadow",
                True,
                (),
            )
        if stage == "shadow":
            return PromotionReview(
                evidence.strategy,
                PromotionDecision.PROMOTE_TO_PAPER,
                "paper",
                True,
                (),
            )
        return PromotionReview(
            evidence.strategy,
            PromotionDecision.HOLD,
            stage,
            True,
            ("manual_approval_required_for_live_execution",),
        )

    def _eligibility_reasons(self, evidence: PromotionEvidence) -> list[str]:
        reasons: list[str] = []
        if evidence.health_score < self.policy.minimum_health_score:
            reasons.append("health_score_below_minimum")
        if evidence.paper_trades < self.policy.minimum_paper_trades:
            reasons.append("insufficient_paper_trades")
        if evidence.out_of_sample_sharpe < self.policy.minimum_out_of_sample_sharpe:
            reasons.append("out_of_sample_sharpe_below_minimum")
        if evidence.maximum_drawdown > self.policy.maximum_drawdown:
            reasons.append("drawdown_above_maximum")
        if evidence.execution_slippage_bps > self.policy.maximum_slippage_bps:
            reasons.append("slippage_above_maximum")
        if evidence.regime_coverage < self.policy.minimum_regime_coverage:
            reasons.append("insufficient_regime_coverage")
        if evidence.consecutive_healthy_reviews < self.policy.minimum_consecutive_reviews:
            reasons.append("insufficient_consecutive_reviews")
        return reasons
