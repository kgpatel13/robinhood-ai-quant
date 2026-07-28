from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.execution.models import AccountSnapshot
from src.execution.short_swing_provider import ShortSwingTargetProvider
from src.strategies.regime import AdaptiveMarketRegimeDetector, AdaptiveRegime
from src.strategies.short_swing import ShortSwingEnsemble


def _bars(start: float, step: float, volatility: float = 0.0, rows: int = 80) -> pd.DataFrame:
    close = [start + step * i + (volatility if i % 2 else -volatility) for i in range(rows)]
    return pd.DataFrame(
        {
            "close": close,
            "high": [value * 1.01 for value in close],
            "volume": [1_000_000 + i * 1_000 for i in range(rows)],
        }
    )


def test_detector_identifies_bullish_regime() -> None:
    bars = {"SPY": _bars(100, 1.0), "AAPL": _bars(80, 0.8), "MSFT": _bars(90, 0.7)}
    assessment = AdaptiveMarketRegimeDetector().detect(bars)
    assert assessment.regime in {AdaptiveRegime.TRENDING_BULL, AdaptiveRegime.RISK_ON}
    assert assessment.confidence > 0.5
    assert assessment.trading_allowed
    assert "momentum" in assessment.allowed_strategies


def test_detector_blocks_bearish_market() -> None:
    bars = {"SPY": _bars(200, -1.5), "AAPL": _bars(180, -1.0), "MSFT": _bars(190, -0.8)}
    assessment = AdaptiveMarketRegimeDetector().detect(bars)
    assert assessment.regime in {AdaptiveRegime.TRENDING_BEAR, AdaptiveRegime.RISK_OFF}
    assert not assessment.trading_allowed


def test_insufficient_data_returns_cash() -> None:
    bars = {"SPY": _bars(100, 1.0, rows=10)}
    provider = ShortSwingTargetProvider(
        lambda _: bars, regime_detector=AdaptiveMarketRegimeDetector()
    )
    account = AccountSnapshot(cash=10_000, equity=10_000, buying_power=10_000, positions=())
    target = provider.generate(datetime.now(UTC), account)
    assert target.weights == {}
    assert "regime=insufficient_data" in target.details


def test_provider_records_regime_and_uses_v2_model() -> None:
    bars = {"SPY": _bars(100, 1.0), "AAPL": _bars(80, 0.8), "MSFT": _bars(90, 0.7)}
    recorded = []
    provider = ShortSwingTargetProvider(
        lambda _: bars,
        regime_detector=AdaptiveMarketRegimeDetector(),
        regime_recorder=lambda _, r: recorded.append(r),
    )
    account = AccountSnapshot(cash=10_000, equity=10_000, buying_power=10_000, positions=())
    target = provider.generate(datetime.now(UTC), account)
    assert target.model_name == "short-swing-ensemble-v2-regime-aware"
    assert recorded
    assert "confidence=" in target.details


def test_ensemble_preserves_legacy_mode_without_regime() -> None:
    bars = {"AAPL": _bars(100, 0.5)}
    ensemble = ShortSwingEnsemble()
    assert ensemble.rank(bars) == ensemble.rank(bars, None)
