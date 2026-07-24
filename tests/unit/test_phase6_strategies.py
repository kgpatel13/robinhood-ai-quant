from __future__ import annotations

import pandas as pd
import pytest

from src.strategies import (
    available_strategies,
    create_strategy,
    strategy_defaults,
    strategy_parameter_space,
)
from src.strategies.ensemble import EnsembleStrategy


def _bars(rows: int = 300) -> pd.DataFrame:
    close = pd.Series([100.0 + index * 0.1 for index in range(rows)])
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close})


def test_all_registered_strategies_generate_bounded_signals() -> None:
    assert len(available_strategies()) == 6
    for name in available_strategies():
        strategy = create_strategy(name, **strategy_defaults(name))
        signals = strategy.generate_signals(_bars())
        assert signals.between(0.0, 1.0).all()
        assert strategy_parameter_space(name)


def test_ensemble_requires_members() -> None:
    with pytest.raises(ValueError):
        EnsembleStrategy(())


def test_invalid_rsi_thresholds_are_rejected() -> None:
    with pytest.raises(ValueError):
        create_strategy("rsi_mean_reversion", period=14, entry_threshold=60.0, exit_threshold=50.0)
