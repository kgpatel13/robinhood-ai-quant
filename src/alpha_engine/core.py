from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class AlphaHorizon(StrEnum):
    SCALPING = "scalping"
    DAY_TRADING = "day_trading"
    SWING = "swing"
    WEEKLY = "weekly"


@dataclass(frozen=True, slots=True)
class AlphaFactorScore:
    name: str
    score: float
    confidence: float
    attribution: float


@dataclass(frozen=True, slots=True)
class AlphaSignal:
    symbol: str
    horizon: AlphaHorizon
    score: float
    confidence: float
    factors: tuple[AlphaFactorScore, ...]


@dataclass(frozen=True, slots=True)
class AlphaConfig:
    momentum_window: int = 20
    reversal_window: int = 5
    volatility_window: int = 20
    volume_window: int = 20
    trend_window: int = 50

    def __post_init__(self) -> None:
        for value in (
            self.momentum_window,
            self.reversal_window,
            self.volatility_window,
            self.volume_window,
            self.trend_window,
        ):
            if value < 2:
                raise ValueError("alpha windows must be at least two")


class AlphaEngine:
    """Builds normalized, explainable alpha signals from OHLCV history."""

    def __init__(self, config: AlphaConfig | None = None) -> None:
        self.config = config or AlphaConfig()

    def evaluate(
        self,
        *,
        symbol: str,
        market: pd.DataFrame,
        horizon: AlphaHorizon,
        regime_multiplier: float = 1.0,
    ) -> AlphaSignal:
        self._validate(market)
        close = pd.to_numeric(market["close"], errors="coerce")
        volume = pd.to_numeric(market["volume"], errors="coerce")
        returns = close.pct_change()

        momentum = self._bounded_return(close, self.config.momentum_window)
        reversal = -self._bounded_return(close, self.config.reversal_window)
        trend = self._trend_score(close)
        relative_volume = self._relative_volume(volume)
        volatility_breakout = self._volatility_breakout(returns)

        raw = {
            "momentum": momentum,
            "reversal": reversal,
            "trend": trend,
            "relative_volume": relative_volume,
            "volatility_breakout": volatility_breakout,
        }
        weights = self._weights(horizon)
        weighted = {name: raw[name] * weights[name] for name in raw}
        score = float(np.clip(sum(weighted.values()) * regime_multiplier, -1.0, 1.0))
        confidence = float(np.clip(np.mean([abs(value) for value in raw.values()]), 0.0, 1.0))
        factors = tuple(
            AlphaFactorScore(
                name=name,
                score=float(raw[name]),
                confidence=float(min(1.0, abs(raw[name]))),
                attribution=float(weighted[name]),
            )
            for name in raw
        )
        return AlphaSignal(symbol.strip().upper(), horizon, score, confidence, factors)

    @staticmethod
    def cross_sectional_rank(signals: tuple[AlphaSignal, ...]) -> dict[str, float]:
        if not signals:
            return {}
        ordered = sorted(signals, key=lambda item: item.score)
        denominator = max(len(ordered) - 1, 1)
        return {
            signal.symbol: (index / denominator) * 2.0 - 1.0
            for index, signal in enumerate(ordered)
        }

    @staticmethod
    def factor_decay(
        scores: pd.Series,
        forward_returns: pd.Series,
        max_lag: int = 10,
    ) -> dict[int, float]:
        if max_lag < 1:
            raise ValueError("max_lag must be positive")
        result: dict[int, float] = {}
        for lag in range(1, max_lag + 1):
            correlation = scores.corr(forward_returns.shift(-lag), method="spearman")
            result[lag] = 0.0 if pd.isna(correlation) else float(correlation)
        return result

    def _trend_score(self, close: pd.Series) -> float:
        short = close.rolling(self.config.momentum_window).mean().iloc[-1]
        long = close.rolling(self.config.trend_window).mean().iloc[-1]
        if pd.isna(short) or pd.isna(long) or long == 0:
            return 0.0
        return float(np.tanh((short / long - 1.0) * 20.0))

    def _relative_volume(self, volume: pd.Series) -> float:
        average = volume.rolling(self.config.volume_window).mean().iloc[-1]
        current = volume.iloc[-1]
        if pd.isna(average) or average <= 0 or pd.isna(current):
            return 0.0
        return float(np.tanh(current / average - 1.0))

    def _volatility_breakout(self, returns: pd.Series) -> float:
        rolling = returns.rolling(self.config.volatility_window).std()
        current = abs(returns.iloc[-1])
        baseline = rolling.iloc[-1]
        direction = np.sign(returns.iloc[-1])
        if pd.isna(current) or pd.isna(baseline) or baseline <= 0:
            return 0.0
        return float(np.tanh(current / baseline - 1.0) * direction)

    @staticmethod
    def _bounded_return(close: pd.Series, window: int) -> float:
        if len(close) <= window:
            return 0.0
        start = close.iloc[-window - 1]
        end = close.iloc[-1]
        if pd.isna(start) or pd.isna(end) or start <= 0:
            return 0.0
        return float(np.tanh((end / start - 1.0) * 10.0))

    @staticmethod
    def _weights(horizon: AlphaHorizon) -> dict[str, float]:
        if horizon is AlphaHorizon.SCALPING:
            return {
                "momentum": 0.20,
                "reversal": 0.20,
                "trend": 0.10,
                "relative_volume": 0.30,
                "volatility_breakout": 0.20,
            }
        if horizon is AlphaHorizon.DAY_TRADING:
            return {
                "momentum": 0.25,
                "reversal": 0.15,
                "trend": 0.15,
                "relative_volume": 0.25,
                "volatility_breakout": 0.20,
            }
        if horizon is AlphaHorizon.SWING:
            return {
                "momentum": 0.30,
                "reversal": 0.10,
                "trend": 0.30,
                "relative_volume": 0.15,
                "volatility_breakout": 0.15,
            }
        return {
            "momentum": 0.30,
            "reversal": 0.05,
            "trend": 0.40,
            "relative_volume": 0.10,
            "volatility_breakout": 0.15,
        }

    @staticmethod
    def _validate(market: pd.DataFrame) -> None:
        required = {"close", "volume"}
        missing = required - set(market.columns)
        if missing:
            raise ValueError(f"missing market columns: {sorted(missing)}")
        if market.empty:
            raise ValueError("market data must not be empty")
