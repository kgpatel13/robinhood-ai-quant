from __future__ import annotations

import pandas as pd

from src.research.phase18.engine import _normalize, _opportunity_components
from src.research.phase18.models import Phase18Config


def _row() -> pd.Series:
    return pd.Series(
        {
            "alpha_probability": 0.66,
            "expected_value": 0.035,
            "execution_score": 0.72,
            "liquidity_score": 0.88,
            "model_recent_win_rate": 0.62,
            "model_recent_mean_return": 0.03,
            "rolling_symbol_correlation": 0.35,
            "phase17_position_fraction": 0.06,
            "incremental_slippage_bps": 2.0,
            "execution_accepted": True,
        }
    )


def test_soft_score_probability_and_sizing_are_bounded() -> None:
    result = _opportunity_components(_row(), Phase18Config())
    assert 0.0 <= float(result["soft_opportunity_score"]) <= 1.0
    assert 0.50 <= float(result["optimized_probability"]) <= 0.75
    assert 0.80 <= float(result["volatility_multiplier"]) <= 1.20


def test_phase17_acceptance_is_preserved_without_new_hard_filter() -> None:
    result = _opportunity_components(_row(), Phase18Config())
    assert result["phase18_accepted"] is True
    assert result["phase18_reason"] == "accepted_soft_weight"


def test_phase17_rejection_is_preserved() -> None:
    row = _row()
    row["execution_accepted"] = False
    result = _opportunity_components(row, Phase18Config())
    assert result["phase18_accepted"] is False
    assert result["phase18_reason"] == "phase17_rejected"


def test_normalize_requires_phase17_columns() -> None:
    try:
        _normalize(pd.DataFrame({"timestamp": ["2020-01-01"]}))
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError")
