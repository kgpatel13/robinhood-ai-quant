from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class SignalDirection(StrEnum):
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    NEUTRAL = "neutral"
    BUY = "buy"
    STRONG_BUY = "strong_buy"


class EntryQuality(StrEnum):
    REJECT = "reject"
    WEAK = "weak"
    ACCEPTABLE = "acceptable"
    STRONG = "strong"
    EXCEPTIONAL = "exceptional"


@dataclass(frozen=True)
class TimeframeConfig:
    weights: Mapping[str, float] | None = None
    minimum_history: int = 50
    confirmation_threshold: float = 0.35
    conflict_penalty: float = 0.25

    def resolved_weights(self) -> dict[str, float]:
        values = dict(
            self.weights
            or {
                "monthly": 0.30,
                "weekly": 0.25,
                "daily": 0.25,
                "hourly": 0.15,
                "intraday": 0.05,
            }
        )
        if not values or any(weight < 0 for weight in values.values()):
            raise ValueError("timeframe weights must be non-negative")
        total = sum(values.values())
        if total <= 0:
            raise ValueError("at least one timeframe weight must be positive")
        return {name: weight / total for name, weight in values.items()}


@dataclass(frozen=True)
class TimeframeSignal:
    timeframe: str
    score: float
    direction: SignalDirection
    trend_strength: float
    momentum: float
    volatility: float
    observations: int


@dataclass(frozen=True)
class MultiTimeframeAssessment:
    symbol: str
    aggregate_score: float
    confirmation_score: float
    conflict_score: float
    direction: SignalDirection
    entry_quality: EntryQuality
    trading_allowed: bool
    signals: tuple[TimeframeSignal, ...]
    reasons: tuple[str, ...]


class MultiTimeframeAnalyzer:
    """Combine independently prepared OHLCV frames into an auditable signal."""

    def __init__(self, config: TimeframeConfig | None = None) -> None:
        self.config = config or TimeframeConfig()

    def assess(self, symbol: str, frames: Mapping[str, pd.DataFrame]) -> MultiTimeframeAssessment:
        weights = self.config.resolved_weights()
        signals: list[TimeframeSignal] = []
        missing: list[str] = []
        for timeframe in weights:
            frame = frames.get(timeframe)
            if frame is None or len(frame) < self.config.minimum_history:
                missing.append(timeframe)
                continue
            signals.append(self._signal(timeframe, frame))

        if not signals:
            return MultiTimeframeAssessment(
                symbol=symbol,
                aggregate_score=0.0,
                confirmation_score=0.0,
                conflict_score=1.0,
                direction=SignalDirection.NEUTRAL,
                entry_quality=EntryQuality.REJECT,
                trading_allowed=False,
                signals=(),
                reasons=("No timeframe has sufficient history",),
            )

        active_weight = sum(weights[item.timeframe] for item in signals)
        aggregate = sum(weights[item.timeframe] * item.score for item in signals) / active_weight
        signs = np.asarray([np.sign(item.score) for item in signals], dtype=float)
        magnitudes = np.asarray([abs(item.score) for item in signals], dtype=float)
        weighted_confirmation = (
            sum(
                weights[item.timeframe]
                * (1.0 if np.sign(item.score) == np.sign(aggregate) else 0.0)
                for item in signals
            )
            / active_weight
        )
        conflict = float(np.average(signs != np.sign(aggregate), weights=magnitudes + 1e-9))
        adjusted = float(
            np.clip(
                aggregate * (1.0 - self.config.conflict_penalty * conflict),
                -1.0,
                1.0,
            )
        )
        direction = self._direction(adjusted)
        quality = self._quality(abs(adjusted), weighted_confirmation, conflict)
        trading_allowed = quality not in {EntryQuality.REJECT, EntryQuality.WEAK}
        reasons = [
            (
                f"{weighted_confirmation:.0%} of active timeframe weight confirms "
                "the aggregate direction"
            ),
            f"conflict score is {conflict:.0%}",
        ]
        if missing:
            reasons.append(f"insufficient history for: {', '.join(missing)}")
        if conflict > 0.40:
            reasons.append("higher/lower timeframe conflict materially reduces entry quality")
        return MultiTimeframeAssessment(
            symbol=symbol,
            aggregate_score=adjusted,
            confirmation_score=float(weighted_confirmation),
            conflict_score=conflict,
            direction=direction,
            entry_quality=quality,
            trading_allowed=trading_allowed,
            signals=tuple(signals),
            reasons=tuple(reasons),
        )

    def _signal(self, timeframe: str, frame: pd.DataFrame) -> TimeframeSignal:
        close = pd.to_numeric(frame["close"], errors="coerce").dropna()
        returns = close.pct_change().dropna()
        fast = close.ewm(span=12, adjust=False).mean()
        slow = close.ewm(span=26, adjust=False).mean()
        trend = float(np.clip((fast.iloc[-1] / slow.iloc[-1] - 1.0) * 20.0, -1.0, 1.0))
        momentum = float(np.clip(close.pct_change(10).iloc[-1] * 8.0, -1.0, 1.0))
        volatility = float(returns.tail(20).std(ddof=0) * np.sqrt(252.0))
        penalty = min(volatility / 1.5, 0.35)
        score = float(np.clip(0.6 * trend + 0.4 * momentum, -1.0, 1.0))
        score *= 1.0 - penalty
        return TimeframeSignal(
            timeframe,
            score,
            self._direction(score),
            abs(trend),
            momentum,
            volatility,
            len(close),
        )

    @staticmethod
    def _direction(score: float) -> SignalDirection:
        if score >= 0.65:
            return SignalDirection.STRONG_BUY
        if score >= 0.15:
            return SignalDirection.BUY
        if score <= -0.65:
            return SignalDirection.STRONG_SELL
        if score <= -0.15:
            return SignalDirection.SELL
        return SignalDirection.NEUTRAL

    @staticmethod
    def _quality(strength: float, confirmation: float, conflict: float) -> EntryQuality:
        composite = strength * 0.60 + confirmation * 0.40 - conflict * 0.25
        if composite >= 0.80:
            return EntryQuality.EXCEPTIONAL
        if composite >= 0.62:
            return EntryQuality.STRONG
        if composite >= 0.45:
            return EntryQuality.ACCEPTABLE
        if composite >= 0.25:
            return EntryQuality.WEAK
        return EntryQuality.REJECT
