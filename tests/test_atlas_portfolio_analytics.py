from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.atlas.portfolio.analytics import (
    AnalyticsConfig,
    analyze_portfolio,
    build_scorecard,
    load_return_matrix,
    write_intelligence_reports,
)
from src.atlas.portfolio.core import TargetPosition


def target(asset_id: str, weight: float, asset_class: str = "stock") -> TargetPosition:
    return TargetPosition(
        asset_id=asset_id,
        symbol=asset_id.split(":", maxsplit=1)[1].upper(),
        asset_class=asset_class,
        rank=1,
        alpha_score=1.0,
        confidence="high",
        target_weight=weight,
        target_value=weight * 100_000,
        estimated_shares=1.0,
    )


def test_analyze_portfolio_produces_risk_metrics() -> None:
    dates = pd.date_range("2025-01-01", periods=100, freq="B")
    returns = pd.DataFrame(
        {
            "stock:A": [0.001] * 100,
            "stock:B": [0.0005 if index % 2 == 0 else -0.0002 for index in range(100)],
        },
        index=dates,
    )
    result = analyze_portfolio(
        [target("stock:A", 0.6), target("stock:B", 0.4)],
        returns,
        1.0,
        AnalyticsConfig(risk_free_rate=0.0),
    )
    assert result.observation_count == 100
    assert result.expected_annual_return is not None
    assert result.annualized_volatility is not None
    assert result.historical_var_95 is not None
    assert result.effective_positions == pytest.approx(1 / (0.6**2 + 0.4**2))


def test_scorecard_is_bounded() -> None:
    dates = pd.date_range("2025-01-01", periods=80, freq="B")
    returns = pd.DataFrame({"stock:A": [0.001] * 80}, index=dates)
    intelligence = analyze_portfolio([target("stock:A", 0.95)], returns, 1.0)
    scorecard = build_scorecard(intelligence)
    assert 0 <= scorecard.overall_score <= 100
    assert scorecard.grade in {"A", "B", "C", "D", "F"}


def test_load_return_matrix_reports_missing_history(tmp_path: Path) -> None:
    history = tmp_path / "daily"
    history.mkdir()
    (history / "stock__A.csv").write_text(
        "timestamp,close\n2025-01-01,100\n2025-01-02,101\n",
        encoding="utf-8",
    )
    matrix, coverage, missing = load_return_matrix(
        [target("stock:A", 0.5), target("stock:B", 0.5)], history
    )
    assert list(matrix.columns) == ["stock:A"]
    assert coverage == 0.5
    assert missing == ("stock:B",)


def test_write_intelligence_reports(tmp_path: Path) -> None:
    dates = pd.date_range("2025-01-01", periods=80, freq="B")
    returns = pd.DataFrame({"stock:A": [0.001] * 80}, index=dates)
    intelligence = analyze_portfolio([target("stock:A", 0.95)], returns, 1.0)
    scorecard = build_scorecard(intelligence)
    paths = write_intelligence_reports(intelligence, scorecard, returns, tmp_path)
    assert set(paths) == {
        "portfolio_intelligence",
        "portfolio_scorecard",
        "correlation_matrix",
        "covariance_matrix",
        "portfolio_dashboard",
    }
    assert (tmp_path / "portfolio_dashboard.html").exists()
