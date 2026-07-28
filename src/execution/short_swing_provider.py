from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

import pandas as pd

from src.execution.models import AccountSnapshot
from src.execution.orchestration import TargetPortfolio
from src.strategies.adaptive_portfolio import AdaptivePortfolioConstructor
from src.strategies.opportunity import MLOpportunityRanker
from src.strategies.regime import AdaptiveMarketRegimeDetector, RegimeAssessment
from src.strategies.short_swing import ShortSwingEnsemble

type ShortSwingBarsProvider = Callable[[datetime], Mapping[str, pd.DataFrame]]
type RegimeRecorder = Callable[[datetime, RegimeAssessment], None]


class ShortSwingTargetProvider:
    """Expose the regime-aware short-swing ensemble to daily orchestration."""

    def __init__(
        self,
        bars_provider: ShortSwingBarsProvider,
        ensemble: ShortSwingEnsemble | None = None,
        *,
        regime_detector: AdaptiveMarketRegimeDetector | None = None,
        benchmark_symbol: str = "SPY",
        regime_recorder: RegimeRecorder | None = None,
        opportunity_ranker: MLOpportunityRanker | None = None,
        portfolio_constructor: AdaptivePortfolioConstructor | None = None,
    ) -> None:
        self.bars_provider = bars_provider
        self.ensemble = ensemble or ShortSwingEnsemble()
        self.regime_detector = regime_detector
        self.benchmark_symbol = benchmark_symbol.upper()
        self.regime_recorder = regime_recorder
        self.opportunity_ranker = opportunity_ranker
        self.portfolio_constructor = portfolio_constructor
        if (opportunity_ranker is None) != (portfolio_constructor is None):
            raise ValueError(
                "opportunity_ranker and portfolio_constructor must be configured together"
            )

    def generate(self, as_of: datetime, account: AccountSnapshot) -> TargetPortfolio:
        del account
        bars = self.bars_provider(as_of)
        if self.regime_detector is None:
            candidates = self.ensemble.rank(bars)
            weights = self.ensemble.target_weights(bars)
            selected = ",".join(candidate.symbol for candidate in candidates[: len(weights)])
            return TargetPortfolio(
                weights,
                model_name="short-swing-ensemble-v1",
                details=f"selected={selected or 'cash'};candidate_count={len(candidates)}",
            )

        regime = self.regime_detector.detect(bars, benchmark_symbol=self.benchmark_symbol)
        if self.regime_recorder is not None:
            self.regime_recorder(as_of, regime)
        candidates = self.ensemble.rank(bars, regime)
        model_name = "short-swing-ensemble-v2-regime-aware"
        ranking_details = ""
        if self.opportunity_ranker is not None and self.portfolio_constructor is not None:
            ranked = self.opportunity_ranker.rank(candidates, regime)
            weights = self.portfolio_constructor.construct(ranked, regime)
            selected = ",".join(
                item.candidate.symbol for item in ranked if item.candidate.symbol in weights
            )
            ranking_source = ranked[0].source if ranked else "none"
            ranking_details = f";ranking={ranking_source};ranked_count={len(ranked)}"
            model_name = "short-swing-ensemble-v3-ml-adaptive"
        else:
            weights = self.ensemble.target_weights(bars, regime)
            selected = ",".join(candidate.symbol for candidate in candidates[: len(weights)])
        components = ",".join(
            f"{name}:{value:.3f}" for name, value in sorted(regime.component_scores.items())
        )
        return TargetPortfolio(
            weights,
            model_name=model_name,
            details=(
                f"regime={regime.regime.value};confidence={regime.confidence:.3f};"
                f"selected={selected or 'cash'};candidate_count={len(candidates)};"
                f"components={components}{ranking_details}"
            ),
        )
