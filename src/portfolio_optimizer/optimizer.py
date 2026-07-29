from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import minimize

from src.portfolio_optimizer.models import (
    OptimizationObjective,
    PortfolioConstraints,
    PortfolioOptimizationResult,
)


class PortfolioOptimizer:
    """Long-only portfolio optimizer with explicit concentration constraints."""

    def optimize(
        self,
        returns: pd.DataFrame,
        objective: OptimizationObjective,
        constraints: PortfolioConstraints | None = None,
    ) -> PortfolioOptimizationResult:
        clean = returns.dropna(how="any")
        if clean.empty or len(clean.columns) < 1:
            raise ValueError("returns must contain at least one complete observation")
        if clean.columns.duplicated().any():
            raise ValueError("asset names must be unique")
        policy = constraints or PortfolioConstraints()
        asset_names = [str(column) for column in clean.columns]
        policy.validate(len(asset_names))
        covariance = np.asarray(clean.cov(), dtype=float)
        covariance = self._regularize(covariance)
        investable = 1.0 - policy.cash_weight
        initial = np.full(len(asset_names), investable / len(asset_names))
        bounds = [(policy.minimum_weight, policy.maximum_weight)] * len(asset_names)
        equality = {"type": "eq", "fun": lambda weights: float(weights.sum() - investable)}

        result = minimize(  # type: ignore[call-overload]
            self._objective(objective, covariance),
            initial,
            method="SLSQP",
            bounds=bounds,
            constraints=(equality,),
            options={"maxiter": 1_000, "ftol": 1e-12},
        )
        weights = np.asarray(result.x if result.success else initial, dtype=float)
        portfolio_variance = float(weights @ covariance @ weights)
        volatility = float(np.sqrt(max(portfolio_variance, 0.0)))
        asset_volatility = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
        weighted_volatility = float(weights @ asset_volatility)
        diversification = weighted_volatility / volatility if volatility > 0 else 0.0
        return PortfolioOptimizationResult(
            objective=objective,
            weights=dict(zip(asset_names, weights, strict=True)),
            cash_weight=policy.cash_weight,
            expected_volatility=volatility,
            diversification_ratio=diversification,
            converged=bool(result.success),
            message=str(result.message),
        )

    @staticmethod
    def _regularize(covariance: NDArray[np.float64]) -> NDArray[np.float64]:
        symmetric = (covariance + covariance.T) / 2.0
        eigenvalues = np.linalg.eigvalsh(symmetric)
        minimum = float(eigenvalues.min())
        if minimum <= 1e-10:
            symmetric += np.eye(len(symmetric)) * (1e-10 - minimum)
        return symmetric

    @staticmethod
    def _objective(
        objective: OptimizationObjective,
        covariance: np.ndarray,
    ) -> Callable[[np.ndarray], float]:
        if objective is OptimizationObjective.MINIMUM_VARIANCE:
            return lambda weights: float(weights @ covariance @ weights)
        if objective is OptimizationObjective.MAXIMUM_DIVERSIFICATION:
            volatility = np.sqrt(np.clip(np.diag(covariance), 0.0, None))

            def negative_diversification(weights: np.ndarray) -> float:
                portfolio_volatility = np.sqrt(max(weights @ covariance @ weights, 1e-18))
                return -float(weights @ volatility / portfolio_volatility)

            return negative_diversification

        def risk_parity_loss(weights: np.ndarray) -> float:
            portfolio_variance = max(float(weights @ covariance @ weights), 1e-18)
            marginal = covariance @ weights
            contributions = weights * marginal / portfolio_variance
            target = np.full(len(weights), 1.0 / len(weights))
            return float(np.square(contributions - target).sum())

        return risk_parity_loss
