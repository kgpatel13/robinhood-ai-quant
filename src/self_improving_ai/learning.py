from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from .models import (
    FeatureCandidate,
    FeatureEvolutionResult,
    LearningPolicy,
    PolicyFeedback,
    StrategyLifecycle,
    StrategyPerformance,
    StrategyUpdate,
)


class StrategyLifecycleManager:
    def __init__(self, policy: LearningPolicy | None = None) -> None:
        self._policy = policy or LearningPolicy()

    def update(self, performance: StrategyPerformance, current_weight: float) -> StrategyUpdate:
        reasons: list[str] = []
        lifecycle = StrategyLifecycle.ACTIVE
        if performance.observations < self._policy.minimum_observations:
            lifecycle = StrategyLifecycle.WATCH
            reasons.append("insufficient observations")
        if performance.sharpe <= self._policy.retirement_sharpe:
            lifecycle = StrategyLifecycle.RETIRED
            reasons.append("sharpe below retirement threshold")
        elif performance.sharpe < self._policy.watch_sharpe:
            lifecycle = StrategyLifecycle.WATCH
            reasons.append("sharpe below active threshold")
        if performance.drawdown > self._policy.maximum_drawdown:
            lifecycle = StrategyLifecycle.RETIRED
            reasons.append("drawdown exceeds limit")

        if lifecycle is StrategyLifecycle.RETIRED:
            new_weight = 0.0
        else:
            score = math.tanh(performance.sharpe) + performance.recent_return
            adjustment = self._policy.learning_rate * score
            new_weight = min(
                self._policy.maximum_weight,
                max(self._policy.minimum_weight, current_weight + adjustment),
            )
        return StrategyUpdate(
            strategy_id=performance.strategy_id,
            lifecycle=lifecycle,
            old_weight=current_weight,
            new_weight=new_weight,
            reasons=tuple(reasons) or ("performance within policy",),
        )


class FeatureEvolutionEngine:
    def select(
        self,
        candidates: Iterable[FeatureCandidate],
        *,
        minimum_predictive_score: float = 0.05,
        minimum_stability_score: float = 0.6,
        maximum_redundancy_score: float = 0.9,
    ) -> FeatureEvolutionResult:
        selected: list[str] = []
        rejected: dict[str, tuple[str, ...]] = {}
        for candidate in candidates:
            reasons: list[str] = []
            if candidate.predictive_score < minimum_predictive_score:
                reasons.append("weak predictive score")
            if candidate.stability_score < minimum_stability_score:
                reasons.append("unstable feature")
            if candidate.redundancy_score > maximum_redundancy_score:
                reasons.append("feature is redundant")
            if reasons:
                rejected[candidate.name] = tuple(reasons)
            else:
                selected.append(candidate.name)
        return FeatureEvolutionResult(selected=tuple(selected), rejected=rejected)


class SafeguardedPolicyUpdater:
    """Bandit-style policy update with bounded weights and risk-adjusted rewards."""

    def __init__(self, learning_rate: float = 0.05, maximum_step: float = 0.1) -> None:
        if learning_rate <= 0.0 or maximum_step <= 0.0:
            raise ValueError("learning_rate and maximum_step must be positive")
        self._learning_rate = learning_rate
        self._maximum_step = maximum_step

    def update(
        self,
        weights: Mapping[str, float],
        feedback: Iterable[PolicyFeedback],
    ) -> dict[str, float]:
        updated = {key: max(0.0, float(value)) for key, value in weights.items()}
        for item in feedback:
            if item.action not in updated:
                continue
            effective_reward = item.reward - max(0.0, item.risk_penalty)
            raw_step = self._learning_rate * effective_reward
            step = max(-self._maximum_step, min(self._maximum_step, raw_step))
            updated[item.action] = max(0.0, updated[item.action] + step)
        total = sum(updated.values())
        if total <= 0.0:
            raise ValueError("policy weights cannot all be zero")
        return {key: value / total for key, value in updated.items()}
