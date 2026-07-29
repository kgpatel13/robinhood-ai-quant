from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class StrategyLifecycle(StrEnum):
    ACTIVE = "active"
    WATCH = "watch"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class StrategyPerformance:
    strategy_id: str
    observations: int
    sharpe: float
    drawdown: float
    win_rate: float
    recent_return: float


@dataclass(frozen=True, slots=True)
class LearningPolicy:
    minimum_observations: int = 30
    retirement_sharpe: float = -0.25
    watch_sharpe: float = 0.25
    maximum_drawdown: float = 0.25
    learning_rate: float = 0.1
    minimum_weight: float = 0.05
    maximum_weight: float = 0.75


@dataclass(frozen=True, slots=True)
class StrategyUpdate:
    strategy_id: str
    lifecycle: StrategyLifecycle
    old_weight: float
    new_weight: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeatureCandidate:
    name: str
    predictive_score: float
    stability_score: float
    redundancy_score: float


@dataclass(frozen=True, slots=True)
class FeatureEvolutionResult:
    selected: tuple[str, ...]
    rejected: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyFeedback:
    action: str
    reward: float
    risk_penalty: float
