from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.atlas.portfolio.core import PortfolioCandidate, PortfolioConfig
from src.atlas.portfolio.optimizer import (
    OptimizerConfig,
    _project_constraints,
    run_optimizer_suite,
    select_correlation_aware_candidates,
)


def candidate(index: int, asset_class: str = "stock") -> PortfolioCandidate:
    return PortfolioCandidate(
        rank=index + 1,
        asset_id=f"{asset_class}:A{index}",
        symbol=f"A{index}",
        asset_class=asset_class,
        alpha_score=1.0 - index * 0.01,
        alpha_percentile=0.99 - index * 0.01,
        confidence="high",
        volatility_60d=0.20 + index * 0.01,
        price=20.0,
        sector=f"Sector{index % 3}",
        industry=f"Industry{index % 5}",
        market_cap=1_000_000_000.0,
        liquidity_score=90.0,
        data_quality_score=95.0,
    )


def test_constraint_projection_respects_limits() -> None:
    candidates = [candidate(index, "crypto" if index < 3 else "stock") for index in range(10)]
    config = PortfolioConfig(
        max_positions=10,
        max_position_pct=0.15,
        max_crypto_pct=0.20,
        max_sector_pct=0.40,
        max_industry_pct=0.30,
        enforce_institutional_eligibility=True,
    )
    projected = _project_constraints(np.ones(10), candidates, config)
    assert abs(float(projected.sum()) - 0.95) < 1e-6
    assert float(projected.max()) <= 0.15 + 1e-8
    assert float(projected[:3].sum()) <= 0.20 + 1e-8


def test_correlation_aware_selection_is_deterministic() -> None:
    candidates = [candidate(index) for index in range(8)]
    rng = np.random.default_rng(42)
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.01, size=(120, 8)),
        columns=[item.asset_id for item in candidates],
    )
    config = PortfolioConfig(max_positions=5, enforce_institutional_eligibility=True)
    optimizer_config = OptimizerConfig(candidate_buffer=8)
    first, _, _ = select_correlation_aware_candidates(
        candidates, returns, config, optimizer_config
    )
    second, _, _ = select_correlation_aware_candidates(
        candidates, returns, config, optimizer_config
    )
    assert [item.asset_id for item in first] == [item.asset_id for item in second]
    assert len(first) == 5


def test_optimizer_suite_runs_all_methods(tmp_path: Path) -> None:
    candidates = [candidate(index, "crypto" if index == 0 else "stock") for index in range(10)]
    rng = np.random.default_rng(7)
    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    for item in candidates:
        daily = rng.normal(0.0004, 0.012 + item.rank * 0.0002, size=len(dates))
        prices = 100.0 * np.cumprod(1.0 + daily)
        pd.DataFrame({"date": dates, "close": prices}).to_csv(
            tmp_path / f"{item.asset_id.replace(':', '__')}.csv", index=False
        )
    config = PortfolioConfig(
        max_positions=8,
        max_position_pct=0.20,
        max_crypto_pct=0.15,
        max_sector_pct=0.50,
        max_industry_pct=0.40,
        enforce_institutional_eligibility=True,
    )
    optimizer_config = OptimizerConfig(candidate_buffer=10)
    result = run_optimizer_suite(candidates, tmp_path, config, optimizer_config)
    assert len(result.methods) == 8
    assert result.selected_method in {item.method for item in result.methods}
    assert all(item.weights for item in result.methods)
    assert all(item.success for item in result.methods)
