from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.atlas.portfolio.core import PortfolioCandidate
from src.atlas.portfolio.execution import (
    ExecutionConfig,
    ExecutionOrder,
    build_orders_from_weights,
    load_daily_dollar_volume,
    simulate_execution,
    write_execution_reports,
)


def _candidate(asset_id: str, asset_class: str = "stock") -> PortfolioCandidate:
    return PortfolioCandidate(
        rank=1,
        asset_id=asset_id,
        symbol=asset_id.split(":")[-1],
        asset_class=asset_class,
        alpha_score=1.0,
        alpha_percentile=0.99,
        confidence="high",
        volatility_60d=0.24,
        price=100.0,
        liquidity_score=95.0,
        data_quality_score=95.0,
    )


def test_execution_is_deterministic_and_costs_are_positive() -> None:
    order = ExecutionOrder(
        asset_id="stock:AAA",
        symbol="AAA",
        asset_class="stock",
        side="buy",
        requested_value=10_000.0,
        reference_price=100.0,
        annual_volatility=0.25,
        daily_dollar_volume=1_000_000.0,
    )
    first = simulate_execution([order])
    second = simulate_execution([order])
    assert first == second
    fill = first.fills[0]
    assert fill.status == "filled"
    assert fill.execution_price > fill.reference_price
    assert fill.total_cost > 0.0
    assert fill.effective_cost_bps > 0.0


def test_capacity_constraint_creates_partial_fill() -> None:
    order = ExecutionOrder(
        asset_id="crypto:BBB",
        symbol="BBB",
        asset_class="crypto",
        side="sell",
        requested_value=100_000.0,
        reference_price=10.0,
        annual_volatility=0.80,
        daily_dollar_volume=100_000.0,
    )
    result = simulate_execution(
        [order],
        ExecutionConfig(maximum_participation_rate=0.05, minimum_fill_ratio=0.01),
    )
    fill = result.fills[0]
    assert fill.status == "partial_fill"
    assert fill.filled_value == pytest.approx(5_000.0)
    assert fill.regulatory_fee > 0.0
    assert result.summary["aggregate_fill_ratio"] == pytest.approx(0.05)


def test_build_orders_and_reports(tmp_path: Path) -> None:
    candidates = [_candidate("stock:AAA"), _candidate("crypto:BBB", "crypto")]
    orders = build_orders_from_weights(
        {"stock:AAA": 0.10, "crypto:BBB": 0.05},
        candidates,
        100_000.0,
        current_weights={"stock:AAA": 0.02},
        daily_dollar_volume={"stock:AAA": 2_000_000.0, "crypto:BBB": 500_000.0},
    )
    assert len(orders) == 2
    result = simulate_execution(orders)
    artifacts = write_execution_reports(result, tmp_path)
    assert all(Path(path).exists() for path in artifacts.values())


def test_load_daily_dollar_volume(tmp_path: Path) -> None:
    pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3),
            "close": [10.0, 11.0, 12.0],
            "volume": [100.0, 200.0, 300.0],
        }
    ).to_csv(tmp_path / "stock__AAA.csv", index=False)
    result = load_daily_dollar_volume(tmp_path, ["stock:AAA"])
    assert result["stock:AAA"] == pytest.approx(2_200.0)
