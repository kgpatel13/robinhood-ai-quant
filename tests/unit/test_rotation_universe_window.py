from __future__ import annotations

import numpy as np
import pandas as pd

from src.rotation_engine.engine import RotationBacktestEngine
from src.rotation_engine.models import AssetClass


def _bars(start: str, rows: int) -> pd.DataFrame:
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


def test_explicit_window_does_not_shift_to_latest_asset_start() -> None:
    engine = RotationBacktestEngine()
    datasets = {
        "OLD": _bars("2023-01-01", 900),
        "NEW": _bars("2024-08-01", 500),
    }
    result = engine.run(
        datasets,
        {"OLD": AssetClass.STOCK, "NEW": AssetClass.STOCK},
        test_start="2025-01-01",
        test_end="2025-12-31",
    )
    start = result.decisions[0]
    assert start["alignment"] == "explicit_test_window_dynamic_eligibility"
    assert str(start["requested_start"]).startswith("2025-01-01")
    assert result.metrics["asset_count"] == 2
