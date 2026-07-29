from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StrategyFamily(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    VOLATILITY = "volatility"
    RELATIVE_STRENGTH = "relative_strength"
    HYBRID = "hybrid"


class SearchMethod(StrEnum):
    GRID = "grid"
    RANDOM = "random"


class PromotionStage(StrEnum):
    RESEARCH = "research"
    SIMULATION = "simulation"
    WALK_FORWARD = "walk_forward"
    PAPER = "paper"
    SHADOW = "shadow"
    SMALL_CAPITAL = "small_capital"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name must not be empty")
        if not self.values:
            raise ValueError("parameter values must not be empty")


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    family: StrategyFamily
    version: str
    parameters: tuple[ParameterSpec, ...] = ()
    description: str = ""
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_id.strip() or not self.name.strip() or not self.version.strip():
            raise ValueError("strategy_id, name and version must not be empty")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("strategy parameter names must be unique")


@dataclass(frozen=True, slots=True)
class RobustnessMetrics:
    out_of_sample_return: float
    walk_forward_sharpe: float
    monte_carlo_survival_rate: float
    parameter_stability: float
    regime_coverage: float
    cost_adjusted_return: float

    def __post_init__(self) -> None:
        bounded = (
            self.monte_carlo_survival_rate,
            self.parameter_stability,
            self.regime_coverage,
        )
        if any(not 0.0 <= value <= 1.0 for value in bounded):
            raise ValueError("robustness rates must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class AlphaCandidate:
    candidate_id: str
    strategy_id: str
    parameters: dict[str, Any]
    total_return: float
    sharpe_ratio: float
    maximum_drawdown: float
    trade_count: int
    robustness: RobustnessMetrics
    score: float = 0.0
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    experiment_id: str
    strategy_id: str
    dataset_id: str
    candidate: AlphaCandidate
    stage: PromotionStage
    fingerprint: str
    metadata: dict[str, Any] = field(default_factory=dict)
