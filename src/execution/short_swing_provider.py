from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

import pandas as pd

from src.execution.models import AccountSnapshot
from src.execution.orchestration import TargetPortfolio
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
    ) -> None:
        self.bars_provider = bars_provider
        self.ensemble = ensemble or ShortSwingEnsemble()
        self.regime_detector = regime_detector
        self.benchmark_symbol = benchmark_symbol.upper()
        self.regime_recorder = regime_recorder

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
        weights = self.ensemble.target_weights(bars, regime)
        selected = ",".join(candidate.symbol for candidate in candidates[: len(weights)])
        components = ",".join(
            f"{name}:{value:.3f}" for name, value in sorted(regime.component_scores.items())
        )
        return TargetPortfolio(
            weights,
            model_name="short-swing-ensemble-v2-regime-aware",
            details=(
                f"regime={regime.regime.value};confidence={regime.confidence:.3f};"
                f"selected={selected or 'cash'};candidate_count={len(candidates)};"
                f"components={components}"
            ),
        )
