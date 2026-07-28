from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from src.strategies.regime import RegimeAssessment


@dataclass(frozen=True)
class ShortSwingCandidate:
    symbol: str
    score: float
    strategy_scores: Mapping[str, float]
    latest_price: float


@dataclass(frozen=True)
class ShortSwingEnsembleConfig:
    lookback: int = 20
    breakout_window: int = 10
    pullback_window: int = 5
    max_positions: int = 5
    min_score: float = 0.55
    cash_reserve: float = 0.10

    def __post_init__(self) -> None:
        if min(self.lookback, self.breakout_window, self.pullback_window) < 2:
            raise ValueError("lookback windows must be at least two")
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if not 0 <= self.min_score <= 1 or not 0 <= self.cash_reserve < 1:
            raise ValueError("invalid ensemble threshold or cash reserve")


class ShortSwingEnsemble:
    """Rank long-only one-to-five-day candidates using normalized rule-based signals."""

    def __init__(self, config: ShortSwingEnsembleConfig | None = None) -> None:
        self.config = config or ShortSwingEnsembleConfig()

    def rank(
        self,
        bars_by_symbol: Mapping[str, pd.DataFrame],
        regime: RegimeAssessment | None = None,
    ) -> tuple[ShortSwingCandidate, ...]:
        candidates: list[ShortSwingCandidate] = []
        required = max(
            self.config.lookback + 1,
            self.config.breakout_window + 1,
            self.config.pullback_window + 2,
        )
        for raw_symbol, bars in bars_by_symbol.items():
            symbol = raw_symbol.upper()
            if len(bars) < required or "close" not in bars or "high" not in bars:
                continue
            close = pd.to_numeric(bars["close"], errors="coerce")
            high = pd.to_numeric(bars["high"], errors="coerce")
            if close.isna().iloc[-1] or high.isna().iloc[-1]:
                continue
            latest = float(close.iloc[-1])
            if latest <= 0:
                continue
            momentum_return = latest / float(close.iloc[-self.config.lookback - 1]) - 1.0
            momentum = self._bounded(0.5 + momentum_return * 2.5)
            prior_high = float(high.iloc[-self.config.breakout_window - 1 : -1].max())
            breakout = self._bounded(0.5 + (latest / prior_high - 1.0) * 20.0)
            recent_peak = float(close.iloc[-self.config.pullback_window - 1 : -1].max())
            pullback_pct = latest / recent_peak - 1.0
            trend = latest / float(close.iloc[-self.config.lookback]) - 1.0
            pullback = self._bounded(0.5 + trend * 3.0 - abs(pullback_pct + 0.02) * 8.0)
            returns = close.pct_change().dropna().tail(self.config.lookback)
            volatility = float(returns.std()) if not returns.empty else 0.0
            quality = self._bounded(1.0 - volatility * 12.0)
            scores = {
                "momentum": momentum,
                "breakout": breakout,
                "pullback": pullback,
                "quality": quality,
            }
            base_weights = {"momentum": 0.35, "breakout": 0.30, "pullback": 0.25, "quality": 0.10}
            if regime is not None:
                allowed = set(regime.allowed_strategies)
                active_weights = {
                    name: weight for name, weight in base_weights.items() if name in allowed
                }
                if not active_weights:
                    continue
                total_weight = sum(active_weights.values())
                score = (
                    sum(scores[name] * weight for name, weight in active_weights.items())
                    / total_weight
                )
                if not regime.trading_allowed:
                    continue
                score *= 0.75 + 0.25 * regime.confidence
            else:
                score = sum(scores[name] * weight for name, weight in base_weights.items())
            if score >= self.config.min_score:
                candidates.append(ShortSwingCandidate(symbol, score, scores, latest))
        return tuple(sorted(candidates, key=lambda candidate: (-candidate.score, candidate.symbol)))

    def target_weights(
        self,
        bars_by_symbol: Mapping[str, pd.DataFrame],
        regime: RegimeAssessment | None = None,
    ) -> dict[str, float]:
        selected = self.rank(bars_by_symbol, regime)[: self.config.max_positions]
        if not selected:
            return {}
        investable = 1.0 - self.config.cash_reserve
        total_score = sum(candidate.score for candidate in selected)
        if total_score <= 0:
            return {}
        return {
            candidate.symbol: investable * candidate.score / total_score for candidate in selected
        }

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, value))
