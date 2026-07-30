from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from src.atlas_finalization.models import (
    ValidationDecision,
    ValidationMetrics,
    ValidationScorecard,
)


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    minimum_sharpe: float = 0.75
    maximum_drawdown: float = 0.20
    minimum_trades: int = 50
    minimum_oos_return: float = 0.0
    minimum_cost_adjusted_return: float = 0.0
    minimum_parameter_stability: float = 0.60
    minimum_regime_coverage: float = 0.50
    promote_score: float = 75.0
    watch_score: float = 55.0


class StrategyValidationEngine:
    def __init__(self, policy: PromotionPolicy | None = None) -> None:
        self.policy = policy or PromotionPolicy()

    def score(self, strategy_id: str, metrics: ValidationMetrics) -> ValidationScorecard:
        checks = (
            (metrics.sharpe_ratio >= self.policy.minimum_sharpe, 20.0, "Sharpe below minimum"),
            (
                metrics.maximum_drawdown <= self.policy.maximum_drawdown,
                15.0,
                "drawdown above maximum",
            ),
            (metrics.trade_count >= self.policy.minimum_trades, 10.0, "insufficient trades"),
            (
                metrics.out_of_sample_return > self.policy.minimum_oos_return,
                20.0,
                "out-of-sample return not positive",
            ),
            (
                metrics.cost_adjusted_return > self.policy.minimum_cost_adjusted_return,
                15.0,
                "edge disappears after costs",
            ),
            (
                metrics.parameter_stability >= self.policy.minimum_parameter_stability,
                10.0,
                "parameter stability below minimum",
            ),
            (
                metrics.regime_coverage >= self.policy.minimum_regime_coverage,
                10.0,
                "regime coverage below minimum",
            ),
        )
        score = sum(weight for passed, weight, _ in checks if passed)
        reasons = tuple(reason for passed, _, reason in checks if not passed)
        if score >= self.policy.promote_score and not reasons:
            decision = ValidationDecision.PROMOTE
        elif score >= self.policy.watch_score:
            decision = ValidationDecision.WATCH
        else:
            decision = ValidationDecision.REJECT
        return ValidationScorecard(strategy_id, score, decision, reasons)


@dataclass(frozen=True, slots=True)
class MonteCarloSummary:
    median_return: float
    fifth_percentile_return: float
    probability_of_loss: float
    worst_drawdown: float


class MonteCarloTradeSimulator:
    @staticmethod
    def simulate(
        trade_returns: Sequence[float],
        *,
        simulations: int = 1_000,
        seed: int = 7,
    ) -> MonteCarloSummary:
        if not trade_returns:
            raise ValueError("trade_returns cannot be empty")
        if simulations < 10:
            raise ValueError("simulations must be at least 10")
        rng = random.Random(seed)
        terminal_returns: list[float] = []
        worst_drawdown = 0.0
        for _ in range(simulations):
            sampled = [rng.choice(trade_returns) for _ in trade_returns]
            equity = 1.0
            peak = 1.0
            path_drawdown = 0.0
            for trade_return in sampled:
                equity *= 1.0 + trade_return
                peak = max(peak, equity)
                path_drawdown = min(path_drawdown, equity / peak - 1.0)
            terminal_returns.append(equity - 1.0)
            worst_drawdown = min(worst_drawdown, path_drawdown)
        ordered = sorted(terminal_returns)
        percentile_index = max(0, int(simulations * 0.05) - 1)
        median = ordered[simulations // 2]
        loss_probability = sum(value < 0 for value in terminal_returns) / simulations
        return MonteCarloSummary(
            median_return=median,
            fifth_percentile_return=ordered[percentile_index],
            probability_of_loss=loss_probability,
            worst_drawdown=abs(worst_drawdown),
        )
