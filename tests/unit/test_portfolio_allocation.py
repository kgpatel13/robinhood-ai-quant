import pandas as pd
import pytest

from src.portfolio.allocation import (
    equal_weights,
    fixed_weights,
    inverse_volatility_weights,
    normalize_weights,
)


def test_equal_weights_sum_to_one() -> None:
    weights = equal_weights(["SPY", "QQQ", "BTC-USD"])
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["SPY"] == pytest.approx(1 / 3)


def test_fixed_weights_validate_symbols() -> None:
    with pytest.raises(ValueError, match="Missing fixed weights"):
        fixed_weights(["SPY", "QQQ"], {"SPY": 1.0})


def test_inverse_volatility_favors_lower_volatility() -> None:
    returns = pd.DataFrame(
        {
            "LOW": [0.01, -0.01, 0.01, -0.01],
            "HIGH": [0.05, -0.05, 0.05, -0.05],
        }
    )
    weights = inverse_volatility_weights(returns, ["LOW", "HIGH"])
    assert weights["LOW"] > weights["HIGH"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_max_weight_cap_is_applied_when_feasible() -> None:
    weights = normalize_weights({"A": 8.0, "B": 1.0, "C": 1.0}, max_asset_weight=0.6)
    assert weights["A"] == pytest.approx(0.6)
    assert sum(weights.values()) == pytest.approx(1.0)
