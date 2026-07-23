from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SearchMethod = Literal["grid", "random"]
ObjectiveName = Literal["sharpe", "cagr", "sortino", "calmar", "profit_factor", "max_drawdown"]


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    values: tuple[int | float, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("parameter name cannot be empty")
        if not self.values:
            raise ValueError(f"parameter {self.name} requires at least one value")


@dataclass(frozen=True)
class OptimizationConfig:
    strategy: str
    parameters: tuple[ParameterSpec, ...]
    method: SearchMethod = "grid"
    objective: ObjectiveName = "sharpe"
    max_evaluations: int | None = None
    seed: int = 42
    workers: int = 1
    initial_cash: float = 100_000.0
    commission_per_trade: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        if not self.parameters:
            raise ValueError("at least one parameter is required")
        if self.workers < 1:
            raise ValueError("workers must be at least 1")
        if self.max_evaluations is not None and self.max_evaluations < 1:
            raise ValueError("max_evaluations must be positive")


@dataclass(frozen=True)
class OptimizationTrial:
    rank: int
    parameters: dict[str, int | float]
    score: float
    metrics: dict[str, float | int]


@dataclass(frozen=True)
class OptimizationResult:
    config: OptimizationConfig
    trials: tuple[OptimizationTrial, ...]
    best_equity_curve: object
    output_directory: Path | None = field(default=None, compare=False)
