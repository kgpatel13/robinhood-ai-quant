from __future__ import annotations

from dataclasses import dataclass

from src.strategies.opportunity import RankedOpportunity
from src.strategies.regime import AdaptiveRegime, RegimeAssessment


@dataclass(frozen=True)
class DynamicSizingConfig:
    max_positions: int = 5
    max_position_weight: float = 0.25
    base_cash_reserve: float = 0.10
    minimum_score: float = 0.55
    concentration_power: float = 1.5

    def __post_init__(self) -> None:
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if not 0 < self.max_position_weight <= 1:
            raise ValueError("max_position_weight must be in (0, 1]")
        if not 0 <= self.base_cash_reserve < 1:
            raise ValueError("base_cash_reserve must be in [0, 1)")
        if not 0 <= self.minimum_score <= 1 or self.concentration_power <= 0:
            raise ValueError("invalid score threshold or concentration power")


class AdaptivePortfolioConstructor:
    """Convert ranked opportunities into confidence- and regime-aware target weights."""

    def __init__(self, config: DynamicSizingConfig | None = None) -> None:
        self.config = config or DynamicSizingConfig()

    def construct(
        self,
        ranked: tuple[RankedOpportunity, ...],
        regime: RegimeAssessment | None = None,
    ) -> dict[str, float]:
        selected = [item for item in ranked if item.final_score >= self.config.minimum_score]
        selected = selected[: self.config.max_positions]
        if not selected:
            return {}
        investable = 1.0 - self._cash_reserve(regime)
        raw = [item.final_score**self.config.concentration_power for item in selected]
        total = sum(raw)
        if total <= 0:
            return {}
        weights = {
            item.candidate.symbol: min(self.config.max_position_weight, investable * value / total)
            for item, value in zip(selected, raw, strict=True)
        }
        used = sum(weights.values())
        # Redistribute unused capital without violating the cap.
        for _ in range(len(weights)):
            remaining = investable - used
            if remaining <= 1e-12:
                break
            eligible = [
                symbol
                for symbol, weight in weights.items()
                if weight < self.config.max_position_weight
            ]
            if not eligible:
                break
            increment = remaining / len(eligible)
            for symbol in eligible:
                weights[symbol] = min(self.config.max_position_weight, weights[symbol] + increment)
            used = sum(weights.values())
        return {symbol: weight for symbol, weight in weights.items() if weight > 0}

    def _cash_reserve(self, regime: RegimeAssessment | None) -> float:
        reserve = self.config.base_cash_reserve
        if regime is None:
            return reserve
        if regime.regime in {AdaptiveRegime.HIGH_VOLATILITY, AdaptiveRegime.RANGE_BOUND}:
            reserve += 0.10
        elif regime.regime is AdaptiveRegime.LOW_VOLATILITY:
            reserve += 0.05
        confidence_penalty = (1.0 - regime.confidence) * 0.20
        return min(0.75, reserve + confidence_penalty)
