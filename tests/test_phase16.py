from __future__ import annotations

import pandas as pd

from src.research.phase16.engine import _adaptive_fraction, _normalize
from src.research.phase16.models import Phase16Config


def test_adaptive_fraction_is_bounded() -> None:
    row = pd.Series(
        {
            "alpha_probability": 0.68,
            "benchmark_volatility_20d": 0.02,
            "predicted_net_return": 0.03,
            "expected_value": 0.02,
            "holding_period": 10,
            "market_regime": "bull_low_volatility",
            "rolling_symbol_correlation": 0.20,
            "model_active": True,
        }
    )
    fraction, components = _adaptive_fraction(row, Phase16Config())
    assert 0.0 <= fraction <= 0.15
    assert components["regime_multiplier"] > 1.0


def test_inactive_model_gets_zero_allocation() -> None:
    row = pd.Series(
        {
            "alpha_probability": 0.70,
            "benchmark_volatility_20d": 0.02,
            "predicted_net_return": 0.04,
            "expected_value": 0.03,
            "holding_period": 5,
            "market_regime": "bull_low_volatility",
            "rolling_symbol_correlation": 0.10,
            "model_active": False,
        }
    )
    fraction, _ = _adaptive_fraction(row, Phase16Config())
    assert fraction == 0.0


def test_normalize_requires_phase15_columns() -> None:
    frame = pd.DataFrame({"timestamp": ["2020-01-01"]})
    try:
        _normalize(frame)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError")
