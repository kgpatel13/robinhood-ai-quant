from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from src.strategy_lab.models import (
    CandidateStatus,
    LaboratoryResult,
    StrategyCandidate,
    StrategyMetrics,
)

Evaluator = Callable[[dict[str, Any]], StrategyMetrics]


@dataclass(frozen=True)
class StrategyLabPolicy:
    minimum_sharpe: float = 0.5
    maximum_drawdown: float = 0.30
    minimum_trades: int = 5
    return_weight: float = 0.30
    sharpe_weight: float = 0.35
    drawdown_weight: float = 0.20
    stability_weight: float = 0.10
    turnover_weight: float = 0.05

    def __post_init__(self) -> None:
        if self.maximum_drawdown <= 0:
            raise ValueError("maximum_drawdown must be positive")
        if self.minimum_trades < 0:
            raise ValueError("minimum_trades cannot be negative")
        weights = (
            self.return_weight,
            self.sharpe_weight,
            self.drawdown_weight,
            self.stability_weight,
            self.turnover_weight,
        )
        if any(weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError("strategy lab weights must be non-negative and sum to positive")


class StrategyLaboratory:
    """Deterministic parameter laboratory with multi-objective candidate ranking."""

    def __init__(self, policy: StrategyLabPolicy | None = None) -> None:
        self.policy = policy or StrategyLabPolicy()

    def run(
        self,
        search_space: Mapping[str, Sequence[Any]],
        evaluator: Evaluator,
    ) -> LaboratoryResult:
        candidates: list[StrategyCandidate] = []
        for index, parameters in enumerate(self._parameter_sets(search_space), start=1):
            metrics = evaluator(parameters)
            reasons = self._rejection_reasons(metrics)
            candidates.append(
                StrategyCandidate(
                    candidate_id=f"candidate-{index:04d}",
                    parameters=parameters,
                    metrics=metrics,
                    score=self._score(metrics),
                    status=(CandidateStatus.REJECTED if reasons else CandidateStatus.CHALLENGER),
                    rejection_reasons=reasons,
                )
            )
        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        for index, candidate in enumerate(ranked):
            if candidate.status is not CandidateStatus.REJECTED:
                ranked[index] = StrategyCandidate(
                    candidate_id=candidate.candidate_id,
                    parameters=candidate.parameters,
                    metrics=candidate.metrics,
                    score=candidate.score,
                    status=CandidateStatus.CHAMPION,
                    rejection_reasons=candidate.rejection_reasons,
                )
                break
        return LaboratoryResult(tuple(ranked))

    @staticmethod
    def _parameter_sets(search_space: Mapping[str, Sequence[Any]]) -> tuple[dict[str, Any], ...]:
        if not search_space:
            return ({},)
        keys = tuple(sorted(search_space))
        values = tuple(tuple(search_space[key]) for key in keys)
        if any(not options for options in values):
            raise ValueError("search-space values cannot be empty")
        return tuple(dict(zip(keys, combination, strict=True)) for combination in product(*values))

    def _rejection_reasons(self, metrics: StrategyMetrics) -> tuple[str, ...]:
        reasons: list[str] = []
        if metrics.sharpe_ratio < self.policy.minimum_sharpe:
            reasons.append("sharpe_below_minimum")
        if abs(metrics.maximum_drawdown) > self.policy.maximum_drawdown:
            reasons.append("drawdown_above_maximum")
        if metrics.trade_count < self.policy.minimum_trades:
            reasons.append("insufficient_trades")
        if metrics.total_return <= 0:
            reasons.append("non_positive_return")
        return tuple(reasons)

    def _score(self, metrics: StrategyMetrics) -> float:
        drawdown_quality = max(0.0, 1.0 - abs(metrics.maximum_drawdown))
        turnover_quality = 1.0 / (1.0 + max(metrics.turnover, 0.0))
        raw = (
            self.policy.return_weight * metrics.total_return
            + self.policy.sharpe_weight * metrics.sharpe_ratio
            + self.policy.drawdown_weight * drawdown_quality
            + self.policy.stability_weight * metrics.regime_stability
            + self.policy.turnover_weight * turnover_quality
        )
        return float(raw)
