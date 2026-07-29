from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class MarketQualityDecision(StrEnum):
    APPROVE = "approve"
    REDUCE = "reduce"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class MicrostructureSnapshot:
    bid: float
    ask: float
    last_price: float
    average_daily_volume: float
    current_volume: float
    order_notional: float
    realized_volatility: float
    minutes_from_open: int


@dataclass(frozen=True, slots=True)
class MicrostructurePolicy:
    maximum_spread_bps: float
    maximum_participation_rate: float
    minimum_relative_volume: float
    maximum_expected_slippage_bps: float

    def __post_init__(self) -> None:
        if self.maximum_spread_bps <= 0:
            raise ValueError("maximum_spread_bps must be positive")
        if not 0 < self.maximum_participation_rate <= 1:
            raise ValueError("maximum_participation_rate must be in (0, 1]")
        if self.minimum_relative_volume < 0:
            raise ValueError("minimum_relative_volume cannot be negative")
        if self.maximum_expected_slippage_bps <= 0:
            raise ValueError("maximum_expected_slippage_bps must be positive")


@dataclass(frozen=True, slots=True)
class MarketQualityReport:
    decision: MarketQualityDecision
    quality_score: float
    spread_bps: float
    relative_volume: float
    participation_rate: float
    expected_slippage_bps: float
    size_multiplier: float
    reasons: tuple[str, ...]


class MicrostructureEvaluator:
    def __init__(self, policy: MicrostructurePolicy) -> None:
        self.policy = policy

    def evaluate(self, snapshot: MicrostructureSnapshot) -> MarketQualityReport:
        self._validate(snapshot)
        midpoint = (snapshot.bid + snapshot.ask) / 2.0
        spread_bps = (snapshot.ask - snapshot.bid) / midpoint * 10_000.0
        relative_volume = snapshot.current_volume / snapshot.average_daily_volume
        participation = snapshot.order_notional / (
            snapshot.average_daily_volume * snapshot.last_price
        )
        open_penalty = max(0.0, (15 - snapshot.minutes_from_open) / 15.0) * 3.0
        expected_slippage = (
            spread_bps / 2.0
            + np.sqrt(participation) * 20.0
            + snapshot.realized_volatility * 10_000.0 * 0.05
            + open_penalty
        )

        reasons: list[str] = []
        severity = 0
        if spread_bps > self.policy.maximum_spread_bps:
            reasons.append("spread exceeds policy")
            severity += 2
        if participation > self.policy.maximum_participation_rate:
            reasons.append("participation rate exceeds policy")
            severity += 2
        if relative_volume < self.policy.minimum_relative_volume:
            reasons.append("relative volume is below policy")
            severity += 1
        if expected_slippage > self.policy.maximum_expected_slippage_bps:
            reasons.append("expected slippage exceeds policy")
            severity += 2

        quality = float(np.clip(1.0 - severity * 0.18, 0.0, 1.0))
        if severity >= 4:
            decision = MarketQualityDecision.REJECT
            multiplier = 0.0
        elif severity > 0:
            decision = MarketQualityDecision.REDUCE
            multiplier = max(0.25, quality)
        else:
            decision = MarketQualityDecision.APPROVE
            multiplier = 1.0
        return MarketQualityReport(
            decision,
            quality,
            float(spread_bps),
            float(relative_volume),
            float(participation),
            float(expected_slippage),
            float(multiplier),
            tuple(reasons),
        )

    @staticmethod
    def _validate(snapshot: MicrostructureSnapshot) -> None:
        if snapshot.bid <= 0 or snapshot.ask <= 0 or snapshot.last_price <= 0:
            raise ValueError("prices must be positive")
        if snapshot.ask < snapshot.bid:
            raise ValueError("ask must be greater than or equal to bid")
        if snapshot.average_daily_volume <= 0:
            raise ValueError("average_daily_volume must be positive")
        if snapshot.current_volume < 0 or snapshot.order_notional < 0:
            raise ValueError("volume and order_notional cannot be negative")


def default_policy(style: str) -> MicrostructurePolicy:
    normalized = style.strip().lower()
    if normalized == "scalping":
        return MicrostructurePolicy(8.0, 0.002, 0.15, 12.0)
    if normalized == "day_trading":
        return MicrostructurePolicy(15.0, 0.005, 0.10, 20.0)
    if normalized == "swing":
        return MicrostructurePolicy(30.0, 0.01, 0.05, 40.0)
    if normalized in {"weekly", "position"}:
        return MicrostructurePolicy(45.0, 0.02, 0.03, 60.0)
    raise ValueError(f"unsupported trading style: {style}")
