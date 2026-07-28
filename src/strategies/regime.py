from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class AdaptiveRegime(StrEnum):
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class RegimeAssessment:
    regime: AdaptiveRegime
    confidence: float
    component_scores: Mapping[str, float]
    allowed_strategies: tuple[str, ...]
    benchmark_symbol: str
    observations: int

    @property
    def trading_allowed(self) -> bool:
        return self.regime not in {
            AdaptiveRegime.TRENDING_BEAR,
            AdaptiveRegime.RISK_OFF,
            AdaptiveRegime.INSUFFICIENT_DATA,
        }


@dataclass(frozen=True)
class AdaptiveRegimeConfig:
    trend_window: int = 50
    momentum_window: int = 20
    volatility_window: int = 20
    breadth_window: int = 20
    high_volatility: float = 0.025
    low_volatility: float = 0.009
    minimum_symbols: int = 3

    def __post_init__(self) -> None:
        if (
            min(
                self.trend_window,
                self.momentum_window,
                self.volatility_window,
                self.breadth_window,
            )
            < 2
        ):
            raise ValueError("regime windows must be at least two")
        if self.minimum_symbols < 1:
            raise ValueError("minimum_symbols must be positive")
        if not 0 < self.low_volatility < self.high_volatility:
            raise ValueError("volatility thresholds must be positive and ordered")


class AdaptiveMarketRegimeDetector:
    """Classify the current market using trend, volatility, breadth, and momentum."""

    def __init__(self, config: AdaptiveRegimeConfig | None = None) -> None:
        self.config = config or AdaptiveRegimeConfig()

    def detect(
        self,
        bars_by_symbol: Mapping[str, pd.DataFrame],
        *,
        benchmark_symbol: str = "SPY",
    ) -> RegimeAssessment:
        benchmark = benchmark_symbol.upper()
        normalized = {symbol.upper(): bars for symbol, bars in bars_by_symbol.items()}
        bars = normalized.get(benchmark)
        required = max(
            self.config.trend_window + 1,
            self.config.momentum_window + 1,
            self.config.volatility_window + 1,
            self.config.breadth_window + 1,
        )
        if bars is None or len(bars) < required or "close" not in bars:
            return self._insufficient(benchmark, len(normalized))

        close = pd.to_numeric(bars["close"], errors="coerce").dropna()
        if len(close) < required or float(close.iloc[-1]) <= 0:
            return self._insufficient(benchmark, len(normalized))

        latest = float(close.iloc[-1])
        trend_average = float(close.tail(self.config.trend_window).mean())
        momentum_return = latest / float(close.iloc[-self.config.momentum_window - 1]) - 1.0
        daily_volatility = float(
            close.pct_change().dropna().tail(self.config.volatility_window).std()
        )
        trend_score = self._bounded(0.5 + (latest / trend_average - 1.0) * 8.0)
        momentum_score = self._bounded(0.5 + momentum_return * 4.0)
        volatility_score = self._bounded(
            (daily_volatility - self.config.low_volatility)
            / (self.config.high_volatility - self.config.low_volatility)
        )
        breadth_score, breadth_observations = self._breadth(normalized)
        volume_score = self._volume_score(bars)

        components = {
            "trend": trend_score,
            "momentum": momentum_score,
            "volatility": volatility_score,
            "breadth": breadth_score,
            "volume": volume_score,
        }
        regime, strength = self._classify(components, daily_volatility)
        confidence = self._bounded(0.45 + strength * 0.45 + min(breadth_observations, 10) * 0.01)
        return RegimeAssessment(
            regime=regime,
            confidence=confidence,
            component_scores=components,
            allowed_strategies=self._allowed_strategies(regime),
            benchmark_symbol=benchmark,
            observations=breadth_observations,
        )

    def _breadth(self, bars_by_symbol: Mapping[str, pd.DataFrame]) -> tuple[float, int]:
        positive = 0
        observed = 0
        for bars in bars_by_symbol.values():
            if "close" not in bars or len(bars) < self.config.breadth_window + 1:
                continue
            close = pd.to_numeric(bars["close"], errors="coerce")
            latest = close.iloc[-1]
            prior = close.iloc[-self.config.breadth_window - 1]
            if pd.isna(latest) or pd.isna(prior) or float(prior) <= 0:
                continue
            observed += 1
            positive += float(latest) > float(prior)
        if observed < self.config.minimum_symbols:
            return 0.5, observed
        return positive / observed, observed

    @staticmethod
    def _volume_score(bars: pd.DataFrame) -> float:
        if "volume" not in bars or len(bars) < 21:
            return 0.5
        volume = pd.to_numeric(bars["volume"], errors="coerce")
        average = float(volume.iloc[-21:-1].mean())
        latest = float(volume.iloc[-1])
        if average <= 0 or pd.isna(average) or pd.isna(latest):
            return 0.5
        return AdaptiveMarketRegimeDetector._bounded(0.5 + (latest / average - 1.0) * 0.25)

    @staticmethod
    def _classify(
        scores: Mapping[str, float], daily_volatility: float
    ) -> tuple[AdaptiveRegime, float]:
        trend = scores["trend"]
        momentum = scores["momentum"]
        breadth = scores["breadth"]
        volatility = scores["volatility"]
        risk_on = 0.40 * trend + 0.35 * momentum + 0.25 * breadth
        risk_off = 1.0 - risk_on

        if daily_volatility >= 0.035 and risk_off >= 0.55:
            return AdaptiveRegime.RISK_OFF, max(daily_volatility / 0.05, risk_off)
        if volatility >= 0.80:
            return AdaptiveRegime.HIGH_VOLATILITY, volatility
        if risk_on >= 0.68 and trend >= 0.62:
            return AdaptiveRegime.TRENDING_BULL, risk_on
        if risk_off >= 0.68 and trend <= 0.38:
            return AdaptiveRegime.TRENDING_BEAR, risk_off
        if risk_on >= 0.58 and breadth >= 0.55:
            return AdaptiveRegime.RISK_ON, risk_on
        if volatility <= 0.18 and abs(trend - 0.5) <= 0.12:
            return AdaptiveRegime.LOW_VOLATILITY, 1.0 - volatility
        return AdaptiveRegime.RANGE_BOUND, 1.0 - abs(risk_on - 0.5)

    @staticmethod
    def _allowed_strategies(regime: AdaptiveRegime) -> tuple[str, ...]:
        return {
            AdaptiveRegime.TRENDING_BULL: ("momentum", "breakout", "pullback", "quality"),
            AdaptiveRegime.TRENDING_BEAR: ("quality",),
            AdaptiveRegime.RANGE_BOUND: ("pullback", "quality"),
            AdaptiveRegime.HIGH_VOLATILITY: ("breakout", "quality"),
            AdaptiveRegime.LOW_VOLATILITY: ("breakout", "pullback", "quality"),
            AdaptiveRegime.RISK_ON: ("momentum", "breakout", "pullback", "quality"),
            AdaptiveRegime.RISK_OFF: ("quality",),
            AdaptiveRegime.INSUFFICIENT_DATA: (),
        }[regime]

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, value))

    @staticmethod
    def _insufficient(benchmark: str, observations: int) -> RegimeAssessment:
        return RegimeAssessment(
            regime=AdaptiveRegime.INSUFFICIENT_DATA,
            confidence=0.0,
            component_scores={
                "trend": 0.5,
                "momentum": 0.5,
                "volatility": 0.5,
                "breadth": 0.5,
                "volume": 0.5,
            },
            allowed_strategies=(),
            benchmark_symbol=benchmark,
            observations=observations,
        )
