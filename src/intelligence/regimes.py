from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class MarketRegime(StrEnum):
    TREND_EXPANSION = "trend_expansion"
    ORDERLY_UPTREND = "orderly_uptrend"
    ORDERLY_DOWNTREND = "orderly_downtrend"
    MEAN_REVERTING = "mean_reverting"
    VOLATILITY_EXPANSION = "volatility_expansion"
    PANIC = "panic"
    RECOVERY = "recovery"
    QUIET = "quiet"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class MarketRegimeAssessment:
    regime: MarketRegime
    confidence: float
    scores: Mapping[str, float]
    preferred_strategy_categories: tuple[str, ...]
    observations: int


@dataclass(frozen=True)
class MarketRegimeConfig:
    trend_window: int = 50
    fast_window: int = 20
    volatility_window: int = 20
    shock_window: int = 5


class MarketRegimeClassifier:
    """Deterministic richer regime classifier suitable for routing strategy plugins."""

    def __init__(self, config: MarketRegimeConfig | None = None) -> None:
        self.config = config or MarketRegimeConfig()

    def classify(self, bars: pd.DataFrame) -> MarketRegimeAssessment:
        required = (
            max(
                self.config.trend_window,
                self.config.fast_window,
                self.config.volatility_window,
            )
            + 2
        )
        if "close" not in bars or len(bars) < required:
            return self._insufficient(len(bars))
        close = pd.to_numeric(bars["close"], errors="coerce").dropna()
        if len(close) < required:
            return self._insufficient(len(close))
        returns = close.pct_change().dropna()
        latest = float(close.iloc[-1])
        slow_average = float(close.tail(self.config.trend_window).mean())
        fast_average = float(close.tail(self.config.fast_window).mean())
        trend = self._bounded(0.5 + (latest / slow_average - 1.0) * 10.0)
        fast_trend = self._bounded(0.5 + (latest / fast_average - 1.0) * 12.0)
        volatility = float(returns.tail(self.config.volatility_window).std(ddof=0))
        prior_volatility = float(
            returns.iloc[-2 * self.config.volatility_window : -self.config.volatility_window].std(
                ddof=0
            )
        )
        volatility_expansion = volatility / prior_volatility if prior_volatility > 0 else 1.0
        shock_return = float(close.pct_change(self.config.shock_window).iloc[-1])
        reversal = float(returns.tail(3).sum()) - float(returns.iloc[-8:-3].sum())
        scores = {
            "trend": trend,
            "fast_trend": fast_trend,
            "volatility": self._bounded(volatility / 0.04),
            "volatility_expansion": self._bounded((volatility_expansion - 0.5) / 1.5),
            "shock": self._bounded(0.5 + shock_return * 8.0),
            "reversal": self._bounded(0.5 + reversal * 8.0),
        }
        regime = self._choose(scores, shock_return, volatility_expansion)
        confidence = self._confidence(regime, scores)
        return MarketRegimeAssessment(
            regime=regime,
            confidence=confidence,
            scores=scores,
            preferred_strategy_categories=self._preferred(regime),
            observations=len(close),
        )

    @staticmethod
    def _choose(
        scores: Mapping[str, float], shock_return: float, volatility_expansion: float
    ) -> MarketRegime:
        trend = scores["trend"]
        fast = scores["fast_trend"]
        volatility = scores["volatility"]
        if shock_return <= -0.08 and volatility >= 0.65:
            return MarketRegime.PANIC
        if scores["reversal"] >= 0.68 and trend <= 0.5:
            return MarketRegime.RECOVERY
        if volatility_expansion >= 1.5 and volatility >= 0.45:
            return MarketRegime.VOLATILITY_EXPANSION
        if trend >= 0.72 and fast >= 0.68:
            return MarketRegime.TREND_EXPANSION
        if trend >= 0.60:
            return MarketRegime.ORDERLY_UPTREND
        if trend <= 0.35 and fast <= 0.40:
            return MarketRegime.ORDERLY_DOWNTREND
        if volatility <= 0.20:
            return MarketRegime.QUIET
        return MarketRegime.MEAN_REVERTING

    @staticmethod
    def _confidence(regime: MarketRegime, scores: Mapping[str, float]) -> float:
        if regime is MarketRegime.INSUFFICIENT_DATA:
            return 0.0
        distance = max(abs(scores["trend"] - 0.5), abs(scores["volatility"] - 0.5))
        return MarketRegimeClassifier._bounded(0.55 + distance * 0.7)

    @staticmethod
    def _preferred(regime: MarketRegime) -> tuple[str, ...]:
        return {
            MarketRegime.TREND_EXPANSION: ("momentum", "breakout"),
            MarketRegime.ORDERLY_UPTREND: ("momentum", "pullback", "quality"),
            MarketRegime.ORDERLY_DOWNTREND: ("defensive", "quality"),
            MarketRegime.MEAN_REVERTING: ("mean_reversion", "quality"),
            MarketRegime.VOLATILITY_EXPANSION: ("breakout", "defensive"),
            MarketRegime.PANIC: ("defensive",),
            MarketRegime.RECOVERY: ("momentum", "quality"),
            MarketRegime.QUIET: ("breakout", "mean_reversion"),
            MarketRegime.INSUFFICIENT_DATA: (),
        }[regime]

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, value))

    @staticmethod
    def _insufficient(observations: int) -> MarketRegimeAssessment:
        return MarketRegimeAssessment(
            regime=MarketRegime.INSUFFICIENT_DATA,
            confidence=0.0,
            scores={},
            preferred_strategy_categories=(),
            observations=observations,
        )
