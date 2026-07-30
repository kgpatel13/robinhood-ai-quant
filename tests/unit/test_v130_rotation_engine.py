from __future__ import annotations

import numpy as np
import pandas as pd

from src.rotation_engine import AssetClass, RotationBacktestEngine, RotationConfig
from src.rotation_engine.strategies import RotationStrategyLibrary


def _bars(seed: int, drift: float, periods: int = 220) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = drift + rng.normal(0.0, 0.012, periods)
    close = 100.0 * np.cumprod(1.0 + returns)
    index = pd.date_range("2025-01-01", periods=periods, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": index,
            "open": close * 0.998,
            "high": close * 1.012,
            "low": close * 0.988,
            "close": close,
            "volume": np.full(periods, 2_000_000.0),
        }
    )


def test_strategy_library_returns_opportunity() -> None:
    bars = _bars(1, 0.002).set_index("timestamp")
    opportunity = RotationStrategyLibrary().assess(
        bars,
        timestamp=bars.index[-1].to_pydatetime(),
        symbol="AAA",
        asset_class=AssetClass.STOCK,
        relative_strength=0.9,
    )
    assert opportunity is not None
    assert 0.0 <= opportunity.score <= 1.0
    assert 1 <= opportunity.expected_holding_days <= 30
    assert opportunity.strategy in {
        "time_series_momentum",
        "donchian_breakout",
        "pullback_continuation",
        "short_term_reversal",
        "relative_strength",
    }


def test_rotation_engine_uses_shared_capital_and_closes_positions() -> None:
    datasets = {
        "AAA": _bars(1, 0.002),
        "BBB": _bars(2, 0.0015),
        "ETH-USD": _bars(3, 0.0025),
    }
    classes = {
        "AAA": AssetClass.STOCK,
        "BBB": AssetClass.STOCK,
        "ETH-USD": AssetClass.CRYPTO,
    }
    result = RotationBacktestEngine().run(
        datasets,
        classes,
        RotationConfig(
            initial_cash=5000,
            max_positions=2,
            min_entry_score=0.50,
            max_hold_days=15,
            no_progress_days=5,
        ),
    )
    assert result.metrics["initial_equity"] == 5000
    assert result.metrics["completed_trades"] > 0
    assert len(result.equity_curve) > 100
    assert all(trade.holding_days <= 15 for trade in result.trades)
    assert any(decision["action"] == "enter" for decision in result.decisions)


def test_emergency_exit_can_happen_before_minimum_hold() -> None:
    bars = _bars(5, 0.003, periods=100)
    bars.loc[70:, "close"] *= 0.60
    bars.loc[70:, "low"] *= 0.55
    datasets = {"AAA": bars, "BBB": _bars(6, 0.001, periods=100)}
    classes = {"AAA": AssetClass.STOCK, "BBB": AssetClass.STOCK}
    result = RotationBacktestEngine().run(
        datasets,
        classes,
        RotationConfig(min_entry_score=0.45, min_hold_days=3, max_hold_days=20),
    )
    assert result.metrics["completed_trades"] > 0


def test_invalid_holding_period_configuration_is_rejected() -> None:
    try:
        RotationConfig(min_hold_days=5, preferred_max_hold_days=3)
    except ValueError as exc:
        assert "holding periods" in str(exc)
    else:
        raise AssertionError("expected ValueError")
