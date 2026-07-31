from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.atlas_v18.ensemble import StrategyVotingEngine
from src.atlas_v18.models import AtlasDecision, PositionSizingInput, StrategySignal
from src.atlas_v18.regime import MarketRegimeEngine
from src.atlas_v18.safety import LiveSafetyLayer, LiveSafetyState
from src.atlas_v18.sizing import DynamicPositionSizer


class AtlasV18DecisionEngine:
    def __init__(
        self,
        *,
        regime_engine: MarketRegimeEngine | None = None,
        voting_engine: StrategyVotingEngine | None = None,
        position_sizer: DynamicPositionSizer | None = None,
        safety_layer: LiveSafetyLayer | None = None,
    ) -> None:
        self.regime_engine = regime_engine or MarketRegimeEngine()
        self.voting_engine = voting_engine or StrategyVotingEngine()
        self.position_sizer = position_sizer or DynamicPositionSizer()
        self.safety_layer = safety_layer or LiveSafetyLayer()

    def evaluate(
        self,
        *,
        prices: Sequence[float],
        signals: Sequence[StrategySignal],
        equity: float,
        current_drawdown: float = 0.0,
        current_exposure_pct: float = 0.0,
        strategy_weights: Mapping[str, float] | None = None,
        safety_state: LiveSafetyState | None = None,
    ) -> AtlasDecision:
        if not prices:
            raise ValueError("prices cannot be empty")
        regime = self.regime_engine.classify(prices)
        ensemble = self.voting_engine.decide(
            signals,
            regime=regime.regime,
            strategy_weights=strategy_weights,
        )
        size = self.position_sizer.size(
            PositionSizingInput(
                equity=equity,
                price=float(prices[-1]),
                confidence=ensemble.confidence,
                annualized_volatility=regime.annualized_volatility,
                current_drawdown=current_drawdown,
                current_exposure_pct=current_exposure_pct,
            )
        )
        state = safety_state or LiveSafetyState(
            position_pct=size.portfolio_pct,
            total_exposure_pct=current_exposure_pct + size.portfolio_pct,
        )
        safety = self.safety_layer.evaluate(ensemble.action, state)
        return AtlasDecision(regime=regime, ensemble=ensemble, size=size, safety=safety)
