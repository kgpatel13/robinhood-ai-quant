from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.continuous_portfolio import (
    ContinuousPaperPortfolio,
    StrategyAction,
    StrategyObservation,
)
from src.regime_intelligence import (
    MarketRegime,
    MarketRegimeClassifier,
    RegimeStrategyGate,
    StrategyRegimePolicy,
)
from src.strategy_lab import CandidateStatus, StrategyLaboratory, StrategyMetrics


def test_strategy_laboratory_selects_best_valid_candidate() -> None:
    laboratory = StrategyLaboratory()

    def evaluate(parameters: dict[str, object]) -> StrategyMetrics:
        fast_value = parameters["fast"]
        assert isinstance(fast_value, int)
        fast = fast_value
        return StrategyMetrics(
            total_return=fast / 100.0,
            sharpe_ratio=fast / 10.0,
            maximum_drawdown=-0.10,
            turnover=0.5,
            trade_count=30,
        )

    result = laboratory.run({"fast": (5, 10, 15)}, evaluate)
    assert result.champion is not None
    assert result.champion.parameters["fast"] == 15
    assert result.champion.status is CandidateStatus.CHAMPION


def test_strategy_laboratory_rejects_unsafe_candidate() -> None:
    result = StrategyLaboratory().run(
        {"window": (10,)},
        lambda _: StrategyMetrics(-0.02, 0.1, -0.45, trade_count=2),
    )
    assert result.candidates[0].status is CandidateStatus.REJECTED
    assert "drawdown_above_maximum" in result.candidates[0].rejection_reasons


def test_regime_classifier_identifies_strong_bull_market() -> None:
    index = pd.date_range("2025-01-01", periods=40, freq="D", tz="UTC")
    bars = pd.DataFrame(
        {
            "close": np.linspace(100.0, 120.0, 40),
            "volume": np.full(40, 1_000_000.0),
        },
        index=index,
    )
    snapshot = MarketRegimeClassifier().classify(bars)
    assert snapshot.regime is MarketRegime.STRONG_BULL
    assert snapshot.confidence >= 0.60


def test_regime_gate_rejects_disallowed_strategy() -> None:
    index = pd.date_range("2025-01-01", periods=40, freq="D", tz="UTC")
    bars = pd.DataFrame(
        {"close": np.linspace(100.0, 120.0, 40), "volume": np.ones(40)}, index=index
    )
    snapshot = MarketRegimeClassifier().classify(bars)
    decision = RegimeStrategyGate().evaluate(
        snapshot,
        StrategyRegimePolicy(frozenset({MarketRegime.SIDEWAYS})),
    )
    assert not decision.approved
    assert decision.size_multiplier == 0.0


def test_continuous_portfolio_promotes_healthy_strategy() -> None:
    portfolio = ContinuousPaperPortfolio()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    portfolio.record(StrategyObservation("momentum", start, 100_000.0, 0.0, 0))
    portfolio.record(
        StrategyObservation(
            "momentum", start + timedelta(days=30), 110_000.0, 10_000.0, 30, 2.0, 2.5
        )
    )
    snapshot = portfolio.snapshot(start + timedelta(days=30))
    assert snapshot.champion == "momentum"
    assert snapshot.strategies[0].action is StrategyAction.PROMOTE


def test_continuous_portfolio_pauses_drawdown_breach() -> None:
    portfolio = ContinuousPaperPortfolio()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    portfolio.record(StrategyObservation("reversal", start, 100_000.0, 0.0, 10))
    portfolio.record(
        StrategyObservation("reversal", start + timedelta(days=1), 70_000.0, -30_000.0, 25)
    )
    snapshot = portfolio.snapshot(start + timedelta(days=1))
    assert snapshot.strategies[0].action is StrategyAction.PAUSE
    assert "drawdown_limit_breached" in snapshot.strategies[0].reasons
