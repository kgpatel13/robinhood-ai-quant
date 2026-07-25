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


def test_drawdown_circuit_breaker_recovers_after_cooldown() -> None:
    timestamps = pd.to_datetime(
        ["2024-01-01", "2024-01-03", "2024-01-04", "2024-02-15", "2024-02-16"],
        utc=True,
    )
    frame = pd.DataFrame(
        {
            "symbol": ["A", "B", "C", "D", "E"],
            "asset_class": ["stock"] * 5,
            "entry_timestamp": timestamps,
            "exit_timestamp": timestamps + pd.Timedelta(days=1),
            "probability": [0.75] * 5,
            "volatility": [0.02] * 5,
            "net_return": [-0.80, 0.01, 0.01, 0.02, 0.02],
        }
    )
    config = Phase13Config(
        target_risk_per_trade=0.01,
        maximum_position_fraction=0.50,
        maximum_gross_exposure=0.50,
        maximum_asset_class_exposure=0.50,
        portfolio_drawdown_limit=0.20,
        recovery_drawdown=0.10,
        drawdown_cooldown_days=30,
    )
    executed, rejected, _, metrics = simulate_portfolio(frame, config)
    assert "D" in set(executed["symbol"])
    assert "drawdown_circuit_breaker" in set(rejected["reason"])
    assert int(metrics["circuit_breaker_resets"]) >= 1


def test_equity_curve_reconciles_every_realized_exit() -> None:
    config = Phase13Config(maximum_open_positions=3)
    executed, _, equity, metrics = simulate_portfolio(_trades(), config)
    expected = config.initial_capital + float(executed["pnl"].sum())
    assert abs(float(metrics["final_capital"]) - expected) <= 1e-8
    assert abs(float(metrics["equity_reconciliation_difference"])) <= 1e-8
    assert abs(float(equity.iloc[-1]["capital"]) - expected) <= 1e-8
    assert int((equity["event"] == "exit").sum()) == len(executed)
