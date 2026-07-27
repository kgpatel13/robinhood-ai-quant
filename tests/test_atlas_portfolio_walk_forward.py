from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.atlas.portfolio.core import PortfolioCandidate, PortfolioConfig
from src.atlas.portfolio.optimizer import OptimizerConfig
from src.atlas.portfolio.walk_forward import (
    WalkForwardConfig,
    run_walk_forward,
    write_walk_forward_reports,
)


def _candidate(index: int, asset_class: str = "stock") -> PortfolioCandidate:
    return PortfolioCandidate(
        rank=index + 1,
        asset_id=f"{asset_class}:W{index}",
        symbol=f"W{index}",
        asset_class=asset_class,
        alpha_score=1.0 - index * 0.01,
        alpha_percentile=0.99 - index * 0.01,
        confidence="high",
        volatility_60d=0.20 + index * 0.01,
        price=25.0,
        sector=f"Sector{index % 4}",
        industry=f"Industry{index % 6}",
        market_cap=2_000_000_000.0,
        liquidity_score=90.0,
        data_quality_score=95.0,
    )


def _history(directory: Path, candidates: list[PortfolioCandidate]) -> None:
    rng = np.random.default_rng(19)
    dates = pd.date_range("2022-01-03", periods=420, freq="B")
    market = rng.normal(0.0003, 0.008, size=len(dates))
    for index, item in enumerate(candidates):
        noise = rng.normal(0.0001, 0.006 + index * 0.0002, size=len(dates))
        daily = 0.55 * market + noise
        prices = 100.0 * np.cumprod(1.0 + daily)
        pd.DataFrame({"date": dates, "close": prices}).to_csv(
            directory / f"{item.asset_id.replace(':', '__')}.csv",
            index=False,
        )


def test_walk_forward_is_deterministic_and_constraint_compliant(tmp_path: Path) -> None:
    candidates = [
        _candidate(index, "crypto" if index == 0 else "stock")
        for index in range(12)
    ]
    _history(tmp_path, candidates)
    portfolio_config = PortfolioConfig(
        max_positions=10,
        max_position_pct=0.20,
        max_crypto_pct=0.15,
        max_sector_pct=0.50,
        max_industry_pct=0.40,
        enforce_institutional_eligibility=True,
    )
    optimizer_config = OptimizerConfig(
        candidate_buffer=12,
        minimum_history_observations=40,
    )
    replay_config = WalkForwardConfig(
        training_observations=180,
        testing_observations=60,
        step_observations=60,
        minimum_windows=3,
        method="auto",
    )
    first = run_walk_forward(
        candidates,
        tmp_path,
        portfolio_config,
        optimizer_config,
        replay_config,
    )
    second = run_walk_forward(
        candidates,
        tmp_path,
        portfolio_config,
        optimizer_config,
        replay_config,
    )
    assert len(first.windows) == 3
    assert first.summary["all_constraints_passed"] is True
    assert first.summary["net_compound_return"] == second.summary["net_compound_return"]
    assert [item.method for item in first.windows] == [item.method for item in second.windows]
    for window in first.windows:
        crypto_weight = sum(
            weight for asset, weight in window.weights.items() if asset.startswith("crypto:")
        )
        assert crypto_weight <= 0.15 + 1e-8


def test_walk_forward_reports_are_written(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    candidates = [_candidate(index) for index in range(8)]
    _history(history_dir, candidates)
    result = run_walk_forward(
        candidates,
        history_dir,
        PortfolioConfig(
            max_positions=8,
            max_position_pct=0.25,
            max_sector_pct=0.60,
            max_industry_pct=0.50,
            enforce_institutional_eligibility=True,
        ),
        OptimizerConfig(candidate_buffer=8, minimum_history_observations=40),
        WalkForwardConfig(
            training_observations=180,
            testing_observations=60,
            step_observations=60,
            minimum_windows=3,
            method="inverse_volatility",
        ),
    )
    artifacts = write_walk_forward_reports(result, tmp_path / "reports")
    assert "walk_forward_summary" in artifacts
    assert "performance_attribution" in artifacts
    assert all(Path(path).exists() for path in artifacts.values())
