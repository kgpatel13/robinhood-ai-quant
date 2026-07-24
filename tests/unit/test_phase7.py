from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase7 import Phase7Config, ScoreWeights, run_phase7_selection
from src.research.phase7.consistency import add_cross_asset_consistency
from src.research.phase7.monte_carlo import simulate_trade_returns
from src.research.phase7.scoring import composite_score


def metrics() -> dict[str, float | int | str | bool]:
    return {
        "oos_total_return": 0.80,
        "oos_sharpe_ratio": 1.20,
        "oos_max_drawdown": -0.18,
        "oos_excess_cagr": 0.04,
        "completed_trades": 55,
        "parameter_stability": 0.80,
        "cost_resilience": 0.90,
        "cross_asset_consistency": 0.75,
        "regime_score": 0.70,
        "monte_carlo_survival": 0.92,
    }


def test_composite_score_is_bounded() -> None:
    score = composite_score(metrics(), ScoreWeights())
    assert 0.0 <= score <= 100.0
    assert score > 70.0


def test_cross_asset_consistency() -> None:
    frame = pd.DataFrame(
        [
            {"strategy": "a", "oos_excess_cagr": 0.1},
            {"strategy": "a", "oos_excess_cagr": -0.1},
            {"strategy": "b", "oos_excess_cagr": 0.2},
        ]
    )
    result = add_cross_asset_consistency(frame)
    assert result.loc[result["strategy"] == "a", "cross_asset_consistency"].iloc[0] == 0.5
    assert result.loc[result["strategy"] == "b", "cross_asset_consistency"].iloc[0] == 1.0


def test_monte_carlo_is_deterministic() -> None:
    first = simulate_trade_returns([0.10, -0.03, 0.05, 0.02], runs=200, seed=7)
    second = simulate_trade_returns([0.10, -0.03, 0.05, 0.02], runs=200, seed=7)
    assert first == second
    assert 0.0 <= first.survival_probability <= 1.0


def test_phase7_generates_reports(tmp_path: Path) -> None:
    source = tmp_path / "tournament.csv"
    row = {"strategy": "alpha", "symbol": "SPY", **metrics()}
    pd.DataFrame([row]).to_csv(source, index=False)
    output = tmp_path / "out"
    result = run_phase7_selection(source, output, Phase7Config(monte_carlo_runs=100))
    assert result["evaluations"] == 1
    assert (output / "phase7_leaderboard.csv").exists()
    assert (output / "promotion_report.json").exists()
    assert (output / "manifest.json").exists()
