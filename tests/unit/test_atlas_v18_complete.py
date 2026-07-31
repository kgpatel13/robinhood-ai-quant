from __future__ import annotations

from math import isclose, isfinite

from src.atlas_v18 import (
    AtlasV18DecisionEngine,
    DynamicPositionSizer,
    LiveSafetyLayer,
    LiveSafetyState,
    MarketRegime,
    MarketRegimeEngine,
    PerformanceAnalytics,
    PositionSizingInput,
    SignalAction,
    StrategySignal,
    StrategyVotingEngine,
)


def test_regime_engine_detects_bull_trend() -> None:
    prices = [100.0 + index for index in range(25)]
    snapshot = MarketRegimeEngine().classify(prices)
    assert snapshot.regime is MarketRegime.TRENDING_BULL
    assert snapshot.confidence > 0


def test_voting_engine_applies_regime_affinity() -> None:
    signals = [
        StrategySignal(
            "trend",
            SignalAction.BUY,
            0.9,
            regime_affinity=frozenset({MarketRegime.TRENDING_BULL}),
        ),
        StrategySignal(
            "reversion",
            SignalAction.SELL,
            0.9,
            regime_affinity=frozenset({MarketRegime.RANGE_BOUND}),
        ),
    ]
    decision = StrategyVotingEngine().decide(signals, regime=MarketRegime.TRENDING_BULL)
    assert decision.action is SignalAction.BUY
    assert decision.weighted_buy > decision.weighted_sell


def test_position_sizer_respects_exposure_cap() -> None:
    result = DynamicPositionSizer(max_total_exposure_pct=0.50).size(
        PositionSizingInput(
            equity=100_000,
            price=100,
            confidence=1.0,
            annualized_volatility=0.20,
            current_exposure_pct=0.49,
        )
    )
    assert result.portfolio_pct <= 0.01 + 1e-12
    assert "max_total_exposure_pct" in result.capped_by


def test_safety_layer_fails_closed_by_default() -> None:
    decision = LiveSafetyLayer().evaluate(SignalAction.BUY, LiveSafetyState())
    assert not decision.allowed
    assert "kill switch enabled" in decision.reasons
    assert "manual approval required" in decision.reasons


def test_performance_analytics_reports_metrics() -> None:
    metrics = PerformanceAnalytics().calculate([100, 102, 101, 104, 107, 106])
    assert metrics.observations == 5
    assert isclose(metrics.total_return, 0.06)
    assert metrics.max_drawdown > 0
    assert isfinite(metrics.sharpe_ratio)


def test_end_to_end_decision_remains_non_live() -> None:
    decision = AtlasV18DecisionEngine().evaluate(
        prices=[100.0 + index for index in range(25)],
        signals=[StrategySignal("momentum", SignalAction.BUY, 0.9)],
        equity=100_000,
    )
    assert decision.ensemble.action is SignalAction.BUY
    assert decision.size.notional > 0
    assert not decision.safety.allowed
