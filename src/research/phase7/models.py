from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

LifecycleState = Literal[
    "REJECTED",
    "EXPERIMENTAL",
    "CANDIDATE",
    "CHALLENGER",
    "CHAMPION",
    "PAPER-TRADING ELIGIBLE",
]


@dataclass(frozen=True)
class ScoreWeights:
    return_score: float = 0.15
    sharpe: float = 0.20
    drawdown: float = 0.15
    benchmark: float = 0.15
    trades: float = 0.10
    stability: float = 0.10
    consistency: float = 0.10
    regime: float = 0.05

    def __post_init__(self) -> None:
        if abs(sum(asdict(self).values()) - 1.0) > 1e-9:
            raise ValueError("score weights must sum to 1.0")


@dataclass(frozen=True)
class PromotionGates:
    minimum_sharpe: float = 0.75
    minimum_excess_cagr: float = 0.0
    maximum_drawdown: float = -0.30
    minimum_trades: int = 20
    minimum_parameter_stability: float = 0.60
    minimum_cost_resilience: float = 0.70
    minimum_cross_asset_consistency: float = 0.50
    minimum_regime_score: float = 0.45
    minimum_monte_carlo_survival: float = 0.80
    minimum_composite_score: float = 70.0


@dataclass(frozen=True)
class Phase7Config:
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    gates: PromotionGates = field(default_factory=PromotionGates)
    seed: int = 42
    monte_carlo_runs: int = 1000
    confidence_level: float = 0.95

    def __post_init__(self) -> None:
        if self.monte_carlo_runs < 100:
            raise ValueError("monte_carlo_runs must be at least 100")
        if not 0.5 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.5 and 1.0")


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    actual: float
    threshold: float
    comparison: str


@dataclass(frozen=True)
class EvaluationResult:
    strategy: str
    symbol: str
    composite_score: float
    lifecycle_state: LifecycleState
    paper_eligible: bool
    gate_results: tuple[GateResult, ...]
    metrics: dict[str, float | int | str | bool]
