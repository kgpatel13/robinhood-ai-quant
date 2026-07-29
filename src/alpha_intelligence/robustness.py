from __future__ import annotations

from dataclasses import dataclass

from src.alpha_intelligence.models import AlphaCandidate


@dataclass(frozen=True, slots=True)
class RobustnessPolicy:
    minimum_sharpe: float = 0.75
    maximum_drawdown: float = 0.25
    minimum_trades: int = 20
    minimum_oos_return: float = 0.0
    minimum_survival_rate: float = 0.70
    minimum_parameter_stability: float = 0.65
    minimum_regime_coverage: float = 0.50
    minimum_cost_adjusted_return: float = 0.0


class RobustnessEvaluator:
    def __init__(self, policy: RobustnessPolicy | None = None) -> None:
        self.policy = policy or RobustnessPolicy()

    def evaluate(self, candidate: AlphaCandidate) -> AlphaCandidate:
        reasons: list[str] = []
        robustness = candidate.robustness
        if candidate.sharpe_ratio < self.policy.minimum_sharpe:
            reasons.append("sharpe_below_minimum")
        if abs(candidate.maximum_drawdown) > self.policy.maximum_drawdown:
            reasons.append("drawdown_above_maximum")
        if candidate.trade_count < self.policy.minimum_trades:
            reasons.append("insufficient_trades")
        if robustness.out_of_sample_return <= self.policy.minimum_oos_return:
            reasons.append("out_of_sample_return_below_minimum")
        if robustness.monte_carlo_survival_rate < self.policy.minimum_survival_rate:
            reasons.append("monte_carlo_survival_below_minimum")
        if robustness.parameter_stability < self.policy.minimum_parameter_stability:
            reasons.append("parameter_stability_below_minimum")
        if robustness.regime_coverage < self.policy.minimum_regime_coverage:
            reasons.append("regime_coverage_below_minimum")
        if robustness.cost_adjusted_return <= self.policy.minimum_cost_adjusted_return:
            reasons.append("cost_adjusted_return_below_minimum")
        score = self._score(candidate)
        return AlphaCandidate(
            candidate_id=candidate.candidate_id,
            strategy_id=candidate.strategy_id,
            parameters=candidate.parameters,
            total_return=candidate.total_return,
            sharpe_ratio=candidate.sharpe_ratio,
            maximum_drawdown=candidate.maximum_drawdown,
            trade_count=candidate.trade_count,
            robustness=robustness,
            score=score,
            rejection_reasons=tuple(reasons),
        )

    @staticmethod
    def _score(candidate: AlphaCandidate) -> float:
        robustness = candidate.robustness
        drawdown_quality = max(0.0, 1.0 - abs(candidate.maximum_drawdown))
        return float(
            0.20 * candidate.total_return
            + 0.20 * candidate.sharpe_ratio
            + 0.10 * drawdown_quality
            + 0.10 * robustness.out_of_sample_return
            + 0.10 * robustness.walk_forward_sharpe
            + 0.10 * robustness.monte_carlo_survival_rate
            + 0.075 * robustness.parameter_stability
            + 0.05 * robustness.regime_coverage
            + 0.025 * robustness.cost_adjusted_return
        )
