from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioConfig:
    capital: float = 100_000.0
    cash_reserve_pct: float = 0.05
    max_positions: int = 25
    max_position_pct: float = 0.08
    max_crypto_pct: float = 0.15
    minimum_alpha_percentile: float = 0.70
    minimum_confidence: str = "medium"
    sizing_method: str = "hybrid"
    rebalance_threshold_pct: float = 0.005
    turnover_limit_pct: float = 0.50

    def __post_init__(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        for name, value in (
            ("cash_reserve_pct", self.cash_reserve_pct),
            ("max_position_pct", self.max_position_pct),
            ("max_crypto_pct", self.max_crypto_pct),
            ("minimum_alpha_percentile", self.minimum_alpha_percentile),
            ("rebalance_threshold_pct", self.rebalance_threshold_pct),
            ("turnover_limit_pct", self.turnover_limit_pct),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if self.sizing_method not in {"equal", "score", "volatility", "hybrid"}:
            raise ValueError("unsupported sizing_method")
        if self.minimum_confidence not in {"low", "medium", "high"}:
            raise ValueError("minimum_confidence must be low, medium, or high")


@dataclass(frozen=True)
class PortfolioCandidate:
    rank: int
    asset_id: str
    symbol: str
    asset_class: str
    alpha_score: float
    alpha_percentile: float
    confidence: str
    volatility_60d: float | None = None
    price: float | None = None


@dataclass(frozen=True)
class TargetPosition:
    asset_id: str
    symbol: str
    asset_class: str
    rank: int
    alpha_score: float
    confidence: str
    target_weight: float
    target_value: float
    estimated_shares: float | None


@dataclass(frozen=True)
class CurrentPosition:
    asset_id: str
    symbol: str
    asset_class: str
    market_value: float


@dataclass(frozen=True)
class RebalanceAction:
    asset_id: str
    symbol: str
    asset_class: str
    action: str
    current_value: float
    target_value: float
    trade_value: float
    current_weight: float
    target_weight: float
    estimated_shares: float | None


@dataclass(frozen=True)
class PortfolioMetrics:
    invested_value: float
    cash_value: float
    cash_weight: float
    position_count: int
    largest_position_weight: float
    crypto_weight: float
    concentration_hhi: float
    effective_positions: float
    estimated_volatility: float | None
    turnover: float


@dataclass(frozen=True)
class PortfolioResult:
    targets: tuple[TargetPosition, ...]
    actions: tuple[RebalanceAction, ...]
    metrics: PortfolioMetrics
    excluded: Mapping[str, str]


def finite_number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def confidence_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value.lower(), -1)


def normalize_weights(raw: Sequence[float], total: float = 1.0) -> list[float]:
    positive = [max(float(value), 0.0) for value in raw]
    denominator = sum(positive)
    if denominator <= 0.0:
        return [total / len(positive)] * len(positive) if positive else []
    return [value / denominator * total for value in positive]
