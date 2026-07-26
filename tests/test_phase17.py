from __future__ import annotations

import pandas as pd

from src.research.phase17.engine import _execution_components, _normalize
from src.research.phase17.models import Phase17Config


def test_execution_score_is_bounded() -> None:
    row = pd.Series(
        {
            "benchmark_volatility_20d": 0.02,
            "adaptive_position_fraction": 0.08,
            "symbol_history_count": 200,
            "rolling_symbol_correlation": 0.2,
            "alpha_probability": 0.68,
            "expected_value": 0.03,
            "asset_class": "stock",
            "market_regime": "bull_low_volatility",
        }
    )
    result = _execution_components(row, Phase17Config())
    assert 0.0 <= float(result["execution_score"]) <= 1.0
    assert float(result["incremental_slippage_bps"]) >= 0.0


def test_zero_allocation_is_rejected() -> None:
    row = pd.Series(
        {
            "benchmark_volatility_20d": 0.02,
            "adaptive_position_fraction": 0.0,
            "symbol_history_count": 200,
            "rolling_symbol_correlation": 0.2,
            "alpha_probability": 0.68,
            "expected_value": 0.03,
            "asset_class": "stock",
            "market_regime": "bull_low_volatility",
        }
    )
    result = _execution_components(row, Phase17Config())
    assert result["execution_accepted"] is False


def test_normalize_requires_phase16_columns() -> None:
    try:
        _normalize(pd.DataFrame({"timestamp": ["2020-01-01"]}))
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError")
