from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.regime_intelligence.models import MarketRegime, RegimeSnapshot


@dataclass(frozen=True)
class RegimeClassifierConfig:
    trend_window: int = 20
    volatility_window: int = 20
    strong_bull_return: float = 0.06
    weak_bull_return: float = 0.015
    panic_return: float = -0.08
    high_volatility: float = 0.35
    low_relative_volume: float = 0.55


class MarketRegimeClassifier:
    def __init__(self, config: RegimeClassifierConfig | None = None) -> None:
        self.config = config or RegimeClassifierConfig()

    def classify(self, bars: pd.DataFrame) -> RegimeSnapshot:
        required = {"close", "volume"}
        missing = required - set(bars.columns)
        if missing:
            raise ValueError(f"bars missing required columns: {sorted(missing)}")
        needed = max(self.config.trend_window, self.config.volatility_window) + 1
        if len(bars) < needed:
            raise ValueError(f"at least {needed} bars are required")
        close = pd.to_numeric(bars["close"], errors="coerce").dropna()
        volume = pd.to_numeric(bars["volume"], errors="coerce").dropna()
        returns = close.pct_change().dropna()
        trend_return = float(close.iloc[-1] / close.iloc[-self.config.trend_window] - 1.0)
        volatility = float(
            returns.tail(self.config.volatility_window).std(ddof=0) * math.sqrt(252)
        )
        recent_volume = float(volume.tail(5).mean())
        baseline_volume = float(volume.tail(self.config.trend_window).mean())
        relative_volume = recent_volume / baseline_volume if baseline_volume > 0 else 0.0
        regime, reasons = self._select(trend_return, volatility, relative_volume)
        confidence = self._confidence(trend_return, volatility, relative_volume, regime)
        return RegimeSnapshot(
            regime=regime,
            confidence=confidence,
            trend_return=trend_return,
            annualized_volatility=volatility,
            relative_volume=relative_volume,
            reasons=reasons,
        )

    def _select(
        self, trend_return: float, volatility: float, relative_volume: float
    ) -> tuple[MarketRegime, tuple[str, ...]]:
        if relative_volume < self.config.low_relative_volume:
            return MarketRegime.LOW_LIQUIDITY, ("relative_volume_below_threshold",)
        if trend_return <= self.config.panic_return and volatility >= self.config.high_volatility:
            return MarketRegime.PANIC, ("large_negative_trend", "elevated_volatility")
        if volatility >= self.config.high_volatility:
            return MarketRegime.HIGH_VOLATILITY, ("volatility_above_threshold",)
        if trend_return >= self.config.strong_bull_return:
            return MarketRegime.STRONG_BULL, ("strong_positive_trend",)
        if trend_return >= self.config.weak_bull_return:
            return MarketRegime.WEAK_BULL, ("positive_trend",)
        if trend_return > 0:
            return MarketRegime.RECOVERY, ("modest_positive_rebound",)
        return MarketRegime.SIDEWAYS, ("trend_below_directional_threshold",)

    def _confidence(
        self,
        trend_return: float,
        volatility: float,
        relative_volume: float,
        regime: MarketRegime,
    ) -> float:
        if regime is MarketRegime.LOW_LIQUIDITY:
            margin = (self.config.low_relative_volume - relative_volume) / max(
                self.config.low_relative_volume, 1e-9
            )
        elif regime in {MarketRegime.HIGH_VOLATILITY, MarketRegime.PANIC}:
            margin = (volatility - self.config.high_volatility) / max(
                self.config.high_volatility, 1e-9
            )
        elif regime is MarketRegime.STRONG_BULL:
            margin = (trend_return - self.config.strong_bull_return) / max(
                self.config.strong_bull_return, 1e-9
            )
        elif regime is MarketRegime.WEAK_BULL:
            margin = (trend_return - self.config.weak_bull_return) / max(
                self.config.weak_bull_return, 1e-9
            )
        else:
            margin = 1.0 - min(abs(trend_return) / max(self.config.weak_bull_return, 1e-9), 1.0)
        return float(min(0.99, max(0.50, 0.60 + 0.30 * max(margin, 0.0))))
