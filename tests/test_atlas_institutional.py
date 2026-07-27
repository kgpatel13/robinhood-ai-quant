from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.atlas.portfolio.analytics import (
    diversification_statistics,
    performance_statistics,
)
from src.atlas.portfolio.institutional import (
    InstitutionalConfig,
    run_institutional_analysis,
)


def test_performance_statistics() -> None:
    stats = performance_statistics(pd.Series([0.01, -0.005, 0.007, 0.002]))
    assert stats["observations"] == 4
    assert stats["annual_volatility"] is not None
    assert stats["maximum_drawdown"] is not None


def test_performance_statistics_winsorizes_bad_market_data() -> None:
    stats = performance_statistics(pd.Series([0.01, 93.0, -0.02, 0.005]))
    assert stats["best_day"] == 0.5
    assert float(stats["annual_volatility"] or 0.0) < 5.0


def test_diversification_statistics() -> None:
    stats = diversification_statistics(pd.Series([0.5, 0.5]))
    assert stats["concentration_hhi"] == 0.5
    assert stats["effective_positions"] == 2.0


def test_institutional_run(tmp_path: Path) -> None:
    portfolio = {
        "positions": [
            {
                "asset_id": "stock:AAA",
                "symbol": "AAA",
                "asset_class": "stock",
                "target_weight": 0.95,
                "price": 10.0,
                "sector": "Technology",
            }
        ]
    }
    orders = {
        "orders": [
            {
                "asset_id": "stock:AAA",
                "action": "BUY",
                "trade_value": 95_000.0,
            }
        ]
    }
    (tmp_path / "portfolio.json").write_text(json.dumps(portfolio))
    (tmp_path / "orders.json").write_text(json.dumps(orders))
    features = pd.DataFrame(
        [
            {
                "asset_id": "stock:AAA",
                "liquidity_score": 100.0,
                "data_quality_score": 100.0,
            }
        ]
    )
    features.to_csv(tmp_path / "features.csv", index=False)
    metadata = pd.DataFrame(
        [{"asset_id": "stock:AAA", "market_cap": 1_000_000_000.0}]
    )
    metadata.to_csv(tmp_path / "metadata.csv", index=False)
    history = tmp_path / "daily"
    history.mkdir()
    dates = pd.date_range("2025-01-01", periods=100)
    asset_history = pd.DataFrame({"date": dates, "close": range(100, 200)})
    asset_history.to_csv(history / "stock__AAA.csv", index=False)
    benchmark = pd.DataFrame({"date": dates, "close": range(200, 300)})
    benchmark.to_csv(tmp_path / "SPY.csv", index=False)
    result = run_institutional_analysis(
        tmp_path / "portfolio.json",
        tmp_path / "orders.json",
        tmp_path / "features.csv",
        tmp_path / "metadata.csv",
        history,
        tmp_path / "SPY.csv",
        tmp_path / "out",
        InstitutionalConfig(monte_carlo_paths=100),
    )
    assert result["complete"] is True
    assert (tmp_path / "out" / "readiness_report.json").exists()
    assert (tmp_path / "out" / "correlation_matrix.csv").exists()
