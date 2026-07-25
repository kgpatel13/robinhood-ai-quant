from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase13.engine import (
    confidence_multiplier,
    run_phase13,
    simulate_portfolio,
    volatility_position_fraction,
)
from src.research.phase13.models import Phase13Config


def _trades() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=20, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": [f"S{i % 5}" for i in range(20)],
            "asset_class": ["stock"] * 20,
            "entry_timestamp": timestamps,
            "exit_timestamp": timestamps + pd.Timedelta(days=2),
            "probability": [0.55 + (i % 4) * 0.05 for i in range(20)],
            "volatility": [0.02] * 20,
            "net_return": [0.01 if i % 3 else -0.005 for i in range(20)],
        }
    )


def test_sizing_is_bounded() -> None:
    config = Phase13Config()
    assert 0.5 <= confidence_multiplier(0.60, config) <= 1.0
    fraction = volatility_position_fraction(0.70, 0.02, config)
    assert 0.0 < fraction <= config.maximum_position_fraction


def test_portfolio_limits_exposure() -> None:
    config = Phase13Config(maximum_open_positions=2, maximum_gross_exposure=0.30)
    executed, rejected, equity, metrics = simulate_portfolio(_trades(), config)
    assert not executed.empty
    assert not equity.empty
    assert float(equity["gross_exposure"].max()) <= 0.3000001
    assert int(metrics["executed_trades"]) == len(executed)
    assert len(rejected) >= 0


def test_phase13_pipeline(tmp_path: Path, monkeypatch) -> None:
    frame = _trades()
    monkeypatch.setattr(pd, "read_csv", lambda _: frame)
    result = run_phase13(
        Phase13Config(
            trades_path=tmp_path / "trades.csv",
            output_root=tmp_path / "reports",
            minimum_trades=1,
        )
    )
    assert result.diagnostics_passed
    assert result.executed_trades > 0
    assert (tmp_path / "reports" / "phase13_final_signoff.json").exists()
