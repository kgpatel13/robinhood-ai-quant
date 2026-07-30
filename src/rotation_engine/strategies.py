from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.rotation_engine.models import AssetClass, Opportunity


@dataclass(frozen=True)
class StrategyEvidence:
    name: str
    category: str
    rationale: str


STRATEGY_EVIDENCE: tuple[StrategyEvidence, ...] = (
    StrategyEvidence(
        "time_series_momentum",
        "momentum",
        "Long-only price persistence adapted to a 1-30 day research horizon.",
    ),
    StrategyEvidence(
        "donchian_breakout",
        "breakout",
        "Channel breakout with volatility and trend confirmation.",
    ),
    StrategyEvidence(
        "pullback_continuation",
        "trend",
        "Buy controlled pullbacks inside an established positive trend.",
    ),
    StrategyEvidence(
        "short_term_reversal",
        "mean_reversion",
        "Liquidity-aware rebound after an unusually weak short-term move.",
    ),
    StrategyEvidence(
        "relative_strength",
        "cross_sectional",
        "Prefer assets with stronger medium-term performance than peers.",
    ),
)


@dataclass(frozen=True)
class StrategyAssessment:
    name: str
    score: float
    expected_holding_days: int
    expected_return: float
    components: Mapping[str, float]


class RotationStrategyLibrary:
    """Research strategy family for long-only positions held roughly 1-30 days."""

    required_history = 65

    def assess(
        self,
        bars: pd.DataFrame,
        *,
        timestamp: datetime,
        symbol: str,
        asset_class: AssetClass,
        relative_strength: float = 0.5,
    ) -> Opportunity | None:
        cutoff = pd.Timestamp(timestamp)
        cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
        clean = bars[bars.index <= cutoff].tail(self.required_history).copy()
        if len(clean) < self.required_history:
            return None
        close = pd.to_numeric(clean["close"], errors="coerce")
        high = pd.to_numeric(clean["high"], errors="coerce")
        low = pd.to_numeric(clean["low"], errors="coerce")
        volume = pd.to_numeric(clean["volume"], errors="coerce")
        if close.isna().any() or high.isna().any() or low.isna().any():
            return None
        price = float(close.iloc[-1])
        if price <= 0:
            return None

        returns = close.pct_change().dropna()
        volatility = float(returns.tail(20).std(ddof=0))
        previous_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
        ).max(axis=1)
        atr = float(true_range.tail(14).mean())
        if atr <= 0:
            return None

        assessments = (
            self._momentum(close, volatility),
            self._breakout(close, high, volume),
            self._pullback(close),
            self._reversal(close, volume, volatility),
            self._relative_strength(close, relative_strength),
        )
        best = max(assessments, key=lambda item: item.score)
        liquidity = self._liquidity_score(price, volume)
        risk_quality = self._bounded(
            1.0 - volatility * (8.0 if asset_class == AssetClass.CRYPTO else 14.0)
        )
        final_score = self._bounded(0.72 * best.score + 0.16 * liquidity + 0.12 * risk_quality)
        if final_score <= 0:
            return None
        components = dict(best.components)
        components.update({"liquidity": liquidity, "risk_quality": risk_quality})
        return Opportunity(
            timestamp=timestamp,
            symbol=symbol,
            asset_class=asset_class,
            strategy=best.name,
            score=final_score,
            expected_holding_days=best.expected_holding_days,
            expected_return=best.expected_return,
            volatility=volatility,
            atr=atr,
            price=price,
            components=components,
        )

    def _momentum(self, close: pd.Series, volatility: float) -> StrategyAssessment:
        ret_5 = float(close.iloc[-1] / close.iloc[-6] - 1.0)
        ret_20 = float(close.iloc[-1] / close.iloc[-21] - 1.0)
        trend = float(close.tail(10).mean() / close.tail(30).mean() - 1.0)
        score = self._bounded(0.48 + ret_5 * 5.0 + ret_20 * 2.2 + trend * 8.0 - volatility * 2.0)
        return StrategyAssessment(
            "time_series_momentum",
            score,
            7,
            max(0.0, 0.35 * ret_5 + 0.20 * ret_20),
            {"ret_5": ret_5, "ret_20": ret_20, "trend": trend},
        )

    def _breakout(self, close: pd.Series, high: pd.Series, volume: pd.Series) -> StrategyAssessment:
        prior_high = float(high.iloc[-21:-1].max())
        breakout = close.iloc[-1] / prior_high - 1.0
        avg_volume = float(volume.iloc[-21:-1].mean())
        relative_volume = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 0.0
        score = self._bounded(0.45 + breakout * 18.0 + (relative_volume - 1.0) * 0.12)
        return StrategyAssessment(
            "donchian_breakout",
            score,
            10,
            max(0.0, breakout * 2.5),
            {"breakout": float(breakout), "relative_volume": relative_volume},
        )

    def _pullback(self, close: pd.Series) -> StrategyAssessment:
        ma_10 = float(close.tail(10).mean())
        ma_30 = float(close.tail(30).mean())
        trend = ma_10 / ma_30 - 1.0
        peak = float(close.tail(10).max())
        pullback = float(close.iloc[-1] / peak - 1.0)
        ideal = 1.0 - min(1.0, abs(pullback + 0.025) / 0.06)
        score = self._bounded(0.35 + trend * 10.0 + ideal * 0.30)
        return StrategyAssessment(
            "pullback_continuation",
            score,
            8,
            max(0.0, trend * 0.8 + ideal * 0.015),
            {"trend": trend, "pullback": pullback, "pullback_quality": ideal},
        )

    def _reversal(
        self, close: pd.Series, volume: pd.Series, volatility: float
    ) -> StrategyAssessment:
        ret_3 = float(close.iloc[-1] / close.iloc[-4] - 1.0)
        long_trend = float(close.iloc[-1] / close.iloc[-31] - 1.0)
        avg_volume = float(volume.iloc[-21:-1].mean())
        relative_volume = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 0.0
        shock = max(0.0, -ret_3 - max(0.02, volatility * 1.5))
        score = self._bounded(
            0.35 + shock * 9.0 + max(0.0, long_trend) * 1.5 - max(0.0, relative_volume - 2.0) * 0.1
        )
        return StrategyAssessment(
            "short_term_reversal",
            score,
            3,
            max(0.0, shock * 0.6),
            {"ret_3": ret_3, "long_trend": long_trend, "shock": shock},
        )

    def _relative_strength(self, close: pd.Series, percentile: float) -> StrategyAssessment:
        ret_20 = float(close.iloc[-1] / close.iloc[-21] - 1.0)
        score = self._bounded(0.35 + percentile * 0.45 + max(0.0, ret_20) * 1.5)
        return StrategyAssessment(
            "relative_strength",
            score,
            15,
            max(0.0, ret_20 * 0.25),
            {"relative_strength_percentile": percentile, "ret_20": ret_20},
        )

    @staticmethod
    def _liquidity_score(price: float, volume: pd.Series) -> float:
        dollar_volume = price * float(volume.tail(20).mean())
        if dollar_volume <= 0:
            return 0.0
        return min(1.0, max(0.0, (math.log10(dollar_volume) - 5.0) / 3.0))

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, float(value)))
