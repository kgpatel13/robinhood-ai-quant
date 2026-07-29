from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.market_intelligence.cross_asset import CrossAssetAnalyzer
from src.market_intelligence.events import EventRiskEngine
from src.market_intelligence.models import (
    CrossAssetSnapshot,
    MarketEvent,
    MarketIntelligenceSnapshot,
    MarketState,
    SectorObservation,
)
from src.market_intelligence.sectors import SectorRotationAnalyzer
from src.market_intelligence.volatility import VolatilityForecaster
from src.regime_intelligence import MarketRegimeClassifier


@dataclass(frozen=True)
class MarketIntelligencePolicy:
    stress_size_multiplier: float = 0.0
    risk_off_size_multiplier: float = 0.45
    neutral_size_multiplier: float = 0.75
    elevated_volatility_multiplier: float = 0.65
    minimum_multiplier: float = 0.0


class MarketIntelligencePlatform:
    def __init__(
        self,
        *,
        regime_classifier: MarketRegimeClassifier | None = None,
        cross_asset_analyzer: CrossAssetAnalyzer | None = None,
        event_risk_engine: EventRiskEngine | None = None,
        sector_analyzer: SectorRotationAnalyzer | None = None,
        volatility_forecaster: VolatilityForecaster | None = None,
        policy: MarketIntelligencePolicy | None = None,
    ) -> None:
        self.regime_classifier = regime_classifier or MarketRegimeClassifier()
        self.cross_asset_analyzer = cross_asset_analyzer or CrossAssetAnalyzer()
        self.event_risk_engine = event_risk_engine or EventRiskEngine()
        self.sector_analyzer = sector_analyzer or SectorRotationAnalyzer()
        self.volatility_forecaster = volatility_forecaster or VolatilityForecaster()
        self.policy = policy or MarketIntelligencePolicy()

    def analyze(
        self,
        *,
        as_of: datetime,
        bars: pd.DataFrame,
        benchmark_returns: pd.Series,
        cross_asset: CrossAssetSnapshot,
        sectors: Iterable[SectorObservation],
        events: Iterable[MarketEvent] = (),
        symbol: str | None = None,
    ) -> MarketIntelligenceSnapshot:
        regime = self.regime_classifier.classify(bars)
        cross = self.cross_asset_analyzer.assess(cross_asset)
        volatility = self.volatility_forecaster.assess(benchmark_returns)
        sector_ranking = self.sector_analyzer.rank(sectors)
        event_risk = self.event_risk_engine.evaluate(
            as_of=as_of,
            symbol=symbol,
            events=events,
        )
        multiplier = self._base_multiplier(cross.state)
        if volatility.elevated:
            multiplier *= self.policy.elevated_volatility_multiplier
        multiplier *= event_risk.size_multiplier
        if not event_risk.approved:
            multiplier = 0.0
        multiplier = min(1.0, max(self.policy.minimum_multiplier, multiplier))
        categories = self._strategy_categories(
            cross.state, regime.regime.value, volatility.elevated
        )
        reasons = (
            f"market_state:{cross.state.value}",
            f"regime:{regime.regime.value}",
            f"volatility_elevated:{str(volatility.elevated).lower()}",
            *event_risk.reasons,
        )
        confidence = min(0.99, (cross.confidence + regime.confidence) / 2.0)
        return MarketIntelligenceSnapshot(
            timestamp=as_of,
            market_state=cross.state,
            confidence=confidence,
            regime=regime.regime.value,
            cross_asset_score=cross.score,
            volatility=volatility,
            sector_ranking=sector_ranking,
            event_risk=event_risk,
            strategy_categories=categories,
            size_multiplier=multiplier,
            reasons=reasons,
        )

    def _base_multiplier(self, state: MarketState) -> float:
        return {
            MarketState.RISK_ON: 1.0,
            MarketState.NEUTRAL: self.policy.neutral_size_multiplier,
            MarketState.RISK_OFF: self.policy.risk_off_size_multiplier,
            MarketState.STRESS: self.policy.stress_size_multiplier,
        }[state]

    @staticmethod
    def _strategy_categories(
        state: MarketState, regime: str, elevated_volatility: bool
    ) -> tuple[str, ...]:
        if state is MarketState.STRESS:
            return ("defensive", "cash")
        if state is MarketState.RISK_OFF:
            return ("defensive", "quality", "mean_reversion")
        if elevated_volatility:
            return ("breakout", "defensive")
        if regime in {"strong_bull", "weak_bull", "recovery"}:
            return ("momentum", "pullback", "relative_strength")
        return ("mean_reversion", "relative_strength")
