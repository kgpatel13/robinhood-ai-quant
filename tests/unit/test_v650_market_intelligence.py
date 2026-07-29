from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.market_intelligence import (
    CrossAssetAnalyzer,
    CrossAssetSnapshot,
    EventRiskEngine,
    EventRiskPolicy,
    EventSeverity,
    EventType,
    MarketEvent,
    MarketIntelligencePlatform,
    MarketState,
    SectorObservation,
    SectorRotationAnalyzer,
    VolatilityForecaster,
)


def _as_of() -> datetime:
    return datetime(2026, 7, 29, 20, 0, tzinfo=UTC)


def _bars() -> pd.DataFrame:
    close = np.linspace(100.0, 120.0, 80)
    return pd.DataFrame({"close": close, "volume": np.full(80, 1_000_000.0)})


def _returns(scale: float = 0.01) -> pd.Series:
    values = np.sin(np.linspace(0.0, 20.0, 120)) * scale
    return pd.Series(values)


def _risk_on_snapshot() -> CrossAssetSnapshot:
    return CrossAssetSnapshot(
        timestamp=_as_of(),
        equity_return=0.04,
        bond_return=0.01,
        dollar_return=-0.01,
        volatility_return=-0.08,
        credit_return=0.02,
    )


def test_cross_asset_risk_on() -> None:
    result = CrossAssetAnalyzer().assess(_risk_on_snapshot())
    assert result.state is MarketState.RISK_ON
    assert result.score > 0.20
    assert result.confidence > 0.50


def test_cross_asset_stress() -> None:
    snapshot = CrossAssetSnapshot(
        timestamp=_as_of(),
        equity_return=-0.08,
        bond_return=-0.03,
        dollar_return=0.04,
        volatility_return=0.20,
        credit_return=-0.04,
    )
    result = CrossAssetAnalyzer().assess(snapshot)
    assert result.state is MarketState.STRESS
    assert result.score <= -0.55


def test_cross_asset_neutral() -> None:
    snapshot = CrossAssetSnapshot(_as_of(), 0.0, 0.0, 0.0, 0.0)
    assert CrossAssetAnalyzer().assess(snapshot).state is MarketState.NEUTRAL


def test_market_event_validates_identifier() -> None:
    with pytest.raises(ValueError, match="event_id"):
        MarketEvent(
            " ",
            EventType.MACRO,
            _as_of(),
            _as_of(),
            EventSeverity.LOW,
            "Event",
        )


def test_market_event_validates_window() -> None:
    with pytest.raises(ValueError, match="ends_at"):
        MarketEvent(
            "bad-window",
            EventType.MACRO,
            _as_of(),
            _as_of() - timedelta(minutes=1),
            EventSeverity.LOW,
            "Event",
        )


def test_event_engine_no_risk() -> None:
    result = EventRiskEngine().evaluate(as_of=_as_of(), symbol="SPY", events=())
    assert result.approved
    assert result.size_multiplier == 1.0


def test_event_engine_blocks_critical() -> None:
    event = MarketEvent(
        "fomc",
        EventType.MACRO,
        _as_of() + timedelta(hours=1),
        _as_of() + timedelta(hours=2),
        EventSeverity.CRITICAL,
        "FOMC decision",
    )
    result = EventRiskEngine().evaluate(as_of=_as_of(), symbol="SPY", events=(event,))
    assert not result.approved
    assert result.size_multiplier == 0.0


def test_event_engine_reduces_high_risk() -> None:
    event = MarketEvent(
        "earnings",
        EventType.EARNINGS,
        _as_of() + timedelta(hours=1),
        _as_of() + timedelta(hours=2),
        EventSeverity.HIGH,
        "Earnings",
        frozenset({"AAPL"}),
    )
    result = EventRiskEngine().evaluate(as_of=_as_of(), symbol="AAPL", events=(event,))
    assert result.approved
    assert result.size_multiplier == 0.5


def test_event_engine_ignores_other_symbol() -> None:
    event = MarketEvent(
        "earnings",
        EventType.EARNINGS,
        _as_of() + timedelta(hours=1),
        _as_of() + timedelta(hours=2),
        EventSeverity.HIGH,
        "Earnings",
        frozenset({"MSFT"}),
    )
    result = EventRiskEngine().evaluate(as_of=_as_of(), symbol="AAPL", events=(event,))
    assert result.size_multiplier == 1.0


def test_event_engine_can_block_high_symbol_event() -> None:
    engine = EventRiskEngine(EventRiskPolicy(block_high_for_symbol=True))
    event = MarketEvent(
        "earnings",
        EventType.EARNINGS,
        _as_of(),
        _as_of() + timedelta(hours=1),
        EventSeverity.HIGH,
        "Earnings",
        frozenset({"AAPL"}),
    )
    assert not engine.evaluate(as_of=_as_of(), symbol="AAPL", events=(event,)).approved


def test_sector_rotation_orders_best_first() -> None:
    rows = (
        SectorObservation("Technology", 0.08, 0.18, 0.20, 0.03),
        SectorObservation("Utilities", 0.02, 0.05, 0.10, 0.03),
        SectorObservation("Energy", -0.01, 0.02, 0.25, 0.03),
    )
    ranking = SectorRotationAnalyzer().rank(rows)
    assert ranking[0].sector == "Technology"
    assert ranking[-1].sector == "Energy"
    assert [row.rank for row in ranking] == [1, 2, 3]


def test_sector_rotation_empty() -> None:
    assert SectorRotationAnalyzer().rank(()) == ()


def test_sector_rotation_handles_zero_volatility() -> None:
    result = SectorRotationAnalyzer().rank((SectorObservation("Cash", 0.01, 0.01, 0.0),))
    assert result[0].risk_adjusted_momentum > 0


def test_volatility_requires_history() -> None:
    with pytest.raises(ValueError, match="at least"):
        VolatilityForecaster().assess(pd.Series([0.01] * 10))


def test_volatility_assessment_is_finite() -> None:
    result = VolatilityForecaster().assess(_returns())
    assert result.annualized_volatility > 0
    assert 0.0 <= result.percentile <= 1.0
    assert result.forecast > 0


def test_volatility_detects_expansion() -> None:
    returns = pd.Series([0.001] * 100 + [0.04, -0.04] * 10)
    result = VolatilityForecaster().assess(returns)
    assert result.elevated
    assert result.expansion_ratio > 1.3


def test_platform_integrates_market_inputs() -> None:
    platform = MarketIntelligencePlatform()
    result = platform.analyze(
        as_of=_as_of(),
        bars=_bars(),
        benchmark_returns=_returns(),
        cross_asset=_risk_on_snapshot(),
        sectors=(SectorObservation("Technology", 0.08, 0.18, 0.20, 0.03),),
        symbol="SPY",
    )
    assert result.market_state is MarketState.RISK_ON
    assert result.size_multiplier > 0
    assert result.sector_ranking[0].sector == "Technology"
    assert result.strategy_categories


def test_platform_blocks_during_critical_event() -> None:
    event = MarketEvent(
        "fomc",
        EventType.MACRO,
        _as_of(),
        _as_of() + timedelta(hours=2),
        EventSeverity.CRITICAL,
        "FOMC",
    )
    result = MarketIntelligencePlatform().analyze(
        as_of=_as_of(),
        bars=_bars(),
        benchmark_returns=_returns(),
        cross_asset=_risk_on_snapshot(),
        sectors=(),
        events=(event,),
    )
    assert result.size_multiplier == 0.0
    assert not result.event_risk.approved


def test_platform_stress_selects_defensive_categories() -> None:
    stress = CrossAssetSnapshot(
        _as_of(),
        equity_return=-0.10,
        bond_return=-0.05,
        dollar_return=0.05,
        volatility_return=0.25,
        credit_return=-0.05,
    )
    result = MarketIntelligencePlatform().analyze(
        as_of=_as_of(),
        bars=_bars(),
        benchmark_returns=_returns(),
        cross_asset=stress,
        sectors=(),
    )
    assert result.size_multiplier == 0.0
    assert result.strategy_categories == ("defensive", "cash")


def test_platform_records_explainable_reasons() -> None:
    result = MarketIntelligencePlatform().analyze(
        as_of=_as_of(),
        bars=_bars(),
        benchmark_returns=_returns(),
        cross_asset=_risk_on_snapshot(),
        sectors=(),
    )
    assert any(reason.startswith("market_state:") for reason in result.reasons)
    assert any(reason.startswith("regime:") for reason in result.reasons)
