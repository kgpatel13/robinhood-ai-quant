from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.rotation_engine.engine import RotationBacktestEngine


def _bars(start: str, rows: int = 100) -> pd.DataFrame:
    index = pd.date_range(start, periods=rows, freq="D", tz="UTC")
    close = np.linspace(100.0, 150.0, rows)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


def test_common_start_uses_latest_asset_after_required_history() -> None:
    engine = RotationBacktestEngine()
    first = _bars("2020-01-01")
    second = _bars("2021-01-01")

    prepared = {"FIRST": engine._prepare(first), "SECOND": engine._prepare(second)}
    start = engine._common_start_timestamp(prepared)

    required = int(getattr(engine.library, "required_history", 65))
    assert start == second.index[required - 1]


def test_metrics_include_extended_validation_fields() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    equity = [(start + timedelta(days=index), 1000.0 + index) for index in range(365)]

    metrics = RotationBacktestEngine._metrics(1000.0, 1364.0, [], equity)

    assert "cagr" in metrics
    assert "sortino_ratio" in metrics
    assert "calmar_ratio" in metrics
    assert "expectancy_per_trade" in metrics
    assert "best_trade" in metrics
    assert "worst_trade" in metrics
