from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase9.features import build_opportunity_features
from src.research.phase9.models import Phase9Config
from src.research.phase9.risk import position_plan
from src.research.phase9.scoring import score_opportunity


def _bars(rows: int = 260) -> pd.DataFrame:
    close = [100.0 + index * 0.25 for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="D", tz="UTC"),
            "symbol": ["TEST"] * rows,
            "open": close,
            "high": [value + 1 for value in close],
            "low": [value - 1 for value in close],
            "close": close,
            "adjusted_close": close,
            "volume": [1_000_000.0] * rows,
        }
    )


def test_features_are_finite() -> None:
    result = build_opportunity_features(_bars())
    assert result["price"] > 0
    assert result["atr"] > 0
    assert result["average_dollar_volume"] > 0


def test_stock_and_crypto_scores_are_bounded() -> None:
    features = build_opportunity_features(_bars())
    stock = score_opportunity(features, "stock")
    crypto = score_opportunity(features, "crypto")
    assert 0 <= stock.total <= 100
    assert 0 <= crypto.total <= 100


def test_position_plan_respects_maximum_weight() -> None:
    profile = Phase9Config().stock_profile
    plan = position_plan(100.0, 2.0, 100_000.0, 80.0, profile)
    assert 0 < plan.weight <= profile.maximum_position_weight
    assert plan.stop_price < 100 < plan.target_price


def test_invalid_configuration_is_rejected(tmp_path: Path) -> None:
    try:
        Phase9Config(top_n_per_market=0, output_root=tmp_path)
    except ValueError as exc:
        assert "top_n_per_market" in str(exc)
    else:
        raise AssertionError("Expected invalid configuration to fail")
