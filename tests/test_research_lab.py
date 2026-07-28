from __future__ import annotations

import numpy as np
import pandas as pd

from src.research_lab import (
    BacktestSettings,
    HistoricalDataService,
    StrategyBacktestEngine,
    WalkForwardEngine,
)
from src.strategies.registry import available_strategies, create_strategy


def bars(length: int = 500) -> pd.DataFrame:
    index = pd.date_range("2023-01-01", periods=length, freq="B", tz="UTC")
    close = 100 + np.linspace(0, 30, length) + np.sin(np.arange(length) / 9) * 4
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(length, 1_000_000.0),
        },
        index=index,
    )


def test_registry_exposes_multiple_strategies() -> None:
    names = available_strategies()
    assert "moving_average_cross" in names
    assert "rsi_mean_reversion" in names
    assert len(names) >= 6


def test_generic_backtest_returns_metrics() -> None:
    result = StrategyBacktestEngine(BacktestSettings(slippage_bps=1.0)).run(
        bars(), create_strategy("moving_average_cross", fast_period=10, slow_period=50)
    )
    assert result.final_equity > 0
    assert len(result.equity_curve) == 500
    assert result.maximum_drawdown <= 0


def test_comparison_summary_contains_each_strategy() -> None:
    comparison = StrategyBacktestEngine().compare(
        bars(), ["moving_average_cross", "rsi_mean_reversion"]
    )
    assert set(comparison.summary()["Strategy"]) == {"moving_average_cross", "rsi_mean_reversion"}


def test_normalization_rejects_missing_columns() -> None:
    frame = pd.DataFrame({"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1))
    try:
        HistoricalDataService.normalize(frame)
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_walk_forward_builds_folds() -> None:
    folds = WalkForwardEngine().run(bars(400), "moving_average_cross", train_size=200, test_size=50)
    assert len(folds) == 4
    assert all(fold.result.final_equity > 0 for fold in folds)
