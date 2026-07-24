from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Phase8Config:
    symbols: tuple[str, ...] = ("SPY", "QQQ", "BTC-USD")
    strategies: tuple[str, ...] = ()
    max_candidates_per_strategy: int = 12
    search_method: Literal["grid", "random", "hybrid"] = "hybrid"
    objective: Literal["sharpe", "cagr", "sortino", "calmar", "profit_factor", "max_drawdown"] = (
        "sharpe"
    )
    seed: int = 42
    workers: int = 1
    initial_cash: float = 100_000.0
    commission_per_trade: float = 0.0
    equity_slippage_bps: float = 2.0
    equity_fee_bps: float = 0.0
    crypto_slippage_bps: float = 10.0
    crypto_fee_bps: float = 25.0
    training_years: int = 5
    testing_years: int = 1
    step_years: int = 1
    minimum_test_rows: int = 100
    neighborhood_score_tolerance: float = 0.25
    minimum_neighbors: int = 1
    monte_carlo_runs: int = 1000
    output_root: Path = Path("reports/phase8")
    database_path: Path = Path("reports/phase8/experiments.sqlite3")
    resume: bool = True

    def __post_init__(self) -> None:
        if self.max_candidates_per_strategy < 1:
            raise ValueError("max_candidates_per_strategy must be positive")
        if self.workers < 1:
            raise ValueError("workers must be at least 1")
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.minimum_neighbors < 0:
            raise ValueError("minimum_neighbors cannot be negative")
        if self.monte_carlo_runs < 100:
            raise ValueError("monte_carlo_runs must be at least 100")


@dataclass(frozen=True)
class CandidateDefinition:
    candidate_id: str
    strategy: str
    parameters: dict[str, int | float]
    source: str


@dataclass(frozen=True)
class GateDiagnostic:
    strategy: str
    symbol: str
    gate: str
    passed: bool
    actual: float
    threshold: float
    comparison: str
    gap: float
    normalized_gap: float


@dataclass(frozen=True)
class CandidateRun:
    experiment_id: str
    candidate: CandidateDefinition
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CACHED"]
    output_directory: Path
    error: str | None = None


@dataclass(frozen=True)
class Phase8Result:
    experiment_id: str
    candidates_generated: int
    candidates_evaluated: int
    candidates_cached: int
    evaluations: int
    eligible: int
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
