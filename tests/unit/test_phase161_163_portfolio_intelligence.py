from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.capital_allocator import (
    AllocationPolicy,
    CapitalAllocationRequest,
    DynamicCapitalAllocator,
    SizingMethod,
)
from src.correlation_engine import CorrelationEngine, CorrelationPolicy
from src.portfolio_optimizer import (
    OptimizationObjective,
    PortfolioConstraints,
    PortfolioOptimizer,
)


def _returns() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    market = rng.normal(0.0005, 0.01, 250)
    return pd.DataFrame(
        {
            "AAPL": market + rng.normal(0.0, 0.003, 250),
            "MSFT": market + rng.normal(0.0, 0.003, 250),
            "TLT": -0.2 * market + rng.normal(0.0, 0.006, 250),
        }
    )


def test_minimum_variance_respects_weight_and_cash_constraints() -> None:
    result = PortfolioOptimizer().optimize(
        _returns(),
        OptimizationObjective.MINIMUM_VARIANCE,
        PortfolioConstraints(maximum_weight=0.60, cash_weight=0.10),
    )
    assert result.converged
    assert sum(result.weights.values()) == pytest.approx(0.90)
    assert max(result.weights.values()) <= 0.60 + 1e-9
    assert result.cash_weight == pytest.approx(0.10)


def test_risk_parity_produces_positive_bounded_weights() -> None:
    result = PortfolioOptimizer().optimize(
        _returns(),
        OptimizationObjective.RISK_PARITY,
        PortfolioConstraints(maximum_weight=0.70),
    )
    assert result.converged
    assert all(weight >= 0.0 for weight in result.weights.values())
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert result.expected_volatility > 0.0


def test_maximum_diversification_reports_ratio() -> None:
    result = PortfolioOptimizer().optimize(
        _returns(),
        OptimizationObjective.MAXIMUM_DIVERSIFICATION,
    )
    assert result.converged
    assert result.diversification_ratio >= 1.0


def test_fractional_kelly_is_confidence_and_limit_adjusted() -> None:
    result = DynamicCapitalAllocator().allocate(
        CapitalAllocationRequest(
            strategy="momentum",
            portfolio_equity=100_000.0,
            confidence=0.80,
            expected_win_probability=0.60,
            payoff_ratio=1.5,
            realized_volatility=0.20,
        ),
        AllocationPolicy(
            method=SizingMethod.FRACTIONAL_KELLY,
            kelly_fraction=0.50,
            maximum_allocation=0.05,
        ),
    )
    assert result.allocation_fraction == pytest.approx(0.05)
    assert result.allocated_capital == pytest.approx(5_000.0)
    assert "maximum_allocation_applied" in result.reasons


def test_drawdown_limit_blocks_allocation() -> None:
    result = DynamicCapitalAllocator().allocate(
        CapitalAllocationRequest(
            strategy="reversal",
            portfolio_equity=50_000.0,
            confidence=0.90,
            expected_win_probability=0.55,
            payoff_ratio=1.2,
            realized_volatility=0.18,
            current_drawdown=0.20,
        ),
    )
    assert result.allocation_fraction == 0.0
    assert result.reasons == ("maximum_drawdown_reached",)


def test_correlation_engine_detects_cluster_and_sector_concentration() -> None:
    report = CorrelationEngine().analyze(
        _returns(),
        weights={"AAPL": 0.35, "MSFT": 0.35, "TLT": 0.30},
        sectors={"AAPL": "technology", "MSFT": "technology", "TLT": "bonds"},
        policy=CorrelationPolicy(
            high_correlation_threshold=0.70,
            maximum_cluster_weight=0.60,
            maximum_sector_weight=0.60,
        ),
    )
    assert any(
        {pair.left, pair.right} == {"AAPL", "MSFT"} for pair in report.highly_correlated_pairs
    )
    assert "sector_technology_weight_exceeds_limit" in report.warnings
    assert 0.0 <= report.diversification_score <= 100.0


def test_correlation_engine_rejects_unknown_weight_asset() -> None:
    with pytest.raises(ValueError, match="unknown assets"):
        CorrelationEngine().analyze(_returns(), {"UNKNOWN": 1.0})
