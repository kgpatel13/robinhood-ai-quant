from __future__ import annotations

from src.research_assistant.models import ResearchPlan, ResearchRequest


class ResearchPlanner:
    """Builds an auditable research workflow from a structured research request."""

    def build(self, request: ResearchRequest) -> ResearchPlan:
        steps = (
            "validate_request_and_data_scope",
            "generate_strategy_candidates",
            "run_in_sample_screening",
            "run_walk_forward_out_of_sample_validation",
            "estimate_execution_costs",
            "evaluate_regime_stability",
            "rank_candidates_against_constraints",
            "record_recommendation_for_manual_review",
        )
        evidence = (
            "total_return",
            "sharpe_ratio",
            "maximum_drawdown",
            "trade_count",
            "regime_coverage",
            "stability",
            "slippage_bps",
            "out_of_sample_status",
        )
        safety = (
            "no_live_order_submission",
            "point_in_time_data_required",
            "out_of_sample_evidence_required",
            "manual_approval_required",
        )
        return ResearchPlan(request.objective, steps, evidence, safety)
