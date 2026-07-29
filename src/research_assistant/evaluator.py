from __future__ import annotations

from src.research_assistant.models import (
    CandidateAssessment,
    CandidateEvidence,
    ResearchConstraints,
    ResearchDecision,
)


class EvidenceEvaluator:
    """Applies deterministic quality gates and multi-objective scoring."""

    def assess(
        self,
        evidence: CandidateEvidence,
        constraints: ResearchConstraints,
    ) -> CandidateAssessment:
        reasons: list[str] = []
        if not evidence.out_of_sample:
            reasons.append("missing_out_of_sample_evidence")
        if evidence.total_return <= 0:
            reasons.append("non_positive_return")
        if evidence.sharpe_ratio < constraints.minimum_sharpe:
            reasons.append("sharpe_below_minimum")
        if evidence.maximum_drawdown > constraints.maximum_drawdown:
            reasons.append("drawdown_above_maximum")
        if evidence.trade_count < constraints.minimum_trades:
            reasons.append("insufficient_trades")
        if evidence.regime_coverage < constraints.minimum_regime_coverage:
            reasons.append("insufficient_regime_coverage")
        if evidence.stability < constraints.minimum_stability:
            reasons.append("stability_below_minimum")
        if evidence.slippage_bps > constraints.maximum_slippage_bps:
            reasons.append("slippage_above_maximum")

        hard_failures = {
            "missing_out_of_sample_evidence",
            "non_positive_return",
            "drawdown_above_maximum",
        }
        if hard_failures.intersection(reasons):
            decision = ResearchDecision.REJECT
        elif reasons:
            decision = ResearchDecision.REVIEW
        else:
            decision = ResearchDecision.RECOMMEND
        return CandidateAssessment(evidence, self._score(evidence), decision, tuple(reasons))

    @staticmethod
    def _score(evidence: CandidateEvidence) -> float:
        drawdown_quality = max(0.0, 1.0 - evidence.maximum_drawdown)
        cost_quality = 1.0 / (1.0 + evidence.slippage_bps / 10.0)
        trade_quality = min(evidence.trade_count / 100.0, 1.0)
        score = (
            0.30 * evidence.sharpe_ratio
            + 0.20 * evidence.total_return
            + 0.20 * drawdown_quality
            + 0.15 * evidence.stability
            + 0.10 * cost_quality
            + 0.05 * trade_quality
        )
        return float(score)
