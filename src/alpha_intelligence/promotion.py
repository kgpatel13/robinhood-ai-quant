from __future__ import annotations

from dataclasses import dataclass

from src.alpha_intelligence.models import AlphaCandidate, PromotionStage


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    current_stage: PromotionStage
    recommended_stage: PromotionStage
    approved: bool
    reasons: tuple[str, ...]


class PromotionPipeline:
    _ORDER = (
        PromotionStage.RESEARCH,
        PromotionStage.SIMULATION,
        PromotionStage.WALK_FORWARD,
        PromotionStage.PAPER,
        PromotionStage.SHADOW,
        PromotionStage.SMALL_CAPITAL,
        PromotionStage.PRODUCTION,
    )

    def recommend(
        self,
        candidate: AlphaCandidate,
        current_stage: PromotionStage,
        manual_approval: bool = False,
    ) -> PromotionDecision:
        reasons: list[str] = []
        if candidate.rejection_reasons:
            reasons.append("candidate_failed_robustness")
        protected_stages = {PromotionStage.SMALL_CAPITAL, PromotionStage.PRODUCTION}
        if current_stage in protected_stages and not manual_approval:
            reasons.append("manual_approval_required")
        approved = not reasons
        index = self._ORDER.index(current_stage)
        next_index = min(index + 1, len(self._ORDER) - 1)
        next_stage = self._ORDER[next_index] if approved else current_stage
        return PromotionDecision(current_stage, next_stage, approved, tuple(reasons))
