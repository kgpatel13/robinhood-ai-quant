from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class OptimizerConfig:
    method: str = "inverse_volatility"
    maximum_weight: float = 0.25
    cash_weight: float = 0.10
    volatility_window: int = 60
    target_portfolio_volatility: float | None = 0.15

    def __post_init__(self) -> None:
        if self.method not in {"equal", "inverse_volatility", "risk_parity"}:
            raise ValueError(f"unsupported optimization method: {self.method}")
        if not 0 < self.maximum_weight <= 1:
            raise ValueError("maximum_weight must be in (0, 1]")
        if not 0 <= self.cash_weight < 1:
            raise ValueError("cash_weight must be in [0, 1)")
        if self.volatility_window < 10:
            raise ValueError("volatility_window must be at least 10")


@dataclass(frozen=True)
class OptimizationResult:
    weights: dict[str, float]
    cash_weight: float
    estimated_volatility: float
    diversification_ratio: float


class PortfolioOptimizer:
    """Long-only optimizer with weight caps and optional volatility targeting."""

    def __init__(self, config: OptimizerConfig | None = None) -> None:
        self.config = config or OptimizerConfig()

    def optimize(self, returns: pd.DataFrame) -> OptimizationResult:
        clean = returns.apply(pd.to_numeric, errors="coerce").dropna(how="all")
        clean = clean.tail(self.config.volatility_window)
        usable = clean.columns[clean.std(ddof=0).fillna(0.0) > 0.0].tolist()
        if not usable:
            return OptimizationResult({}, 1.0, 0.0, 0.0)
        selected = clean[usable].dropna()
        if len(selected) < 2:
            return OptimizationResult({}, 1.0, 0.0, 0.0)
        raw: FloatArray
        if self.config.method == "equal":
            raw = np.ones(len(usable), dtype=np.float64)
        else:
            covariance = np.asarray(
                selected.cov(ddof=0).to_numpy(dtype=np.float64) * 252.0,
                dtype=np.float64,
            )
            volatility = np.asarray(
                np.sqrt(np.clip(np.diag(covariance), 1e-12, None)),
                dtype=np.float64,
            )
            raw = np.asarray(1.0 / volatility, dtype=np.float64)
            if self.config.method == "risk_parity":
                initial = np.asarray(raw / float(raw.sum()), dtype=np.float64)
                raw = self._risk_parity(covariance, initial)
        invested_target = 1.0 - self.config.cash_weight
        weights = self._cap_and_normalize(raw, usable, invested_target)
        vector = np.asarray([weights[symbol] for symbol in usable], dtype=float)
        covariance = np.asarray(
            selected.cov(ddof=0).to_numpy(dtype=np.float64) * 252.0,
            dtype=np.float64,
        )
        portfolio_volatility = float(np.sqrt(max(vector @ covariance @ vector, 0.0)))
        if (
            self.config.target_portfolio_volatility is not None
            and portfolio_volatility > self.config.target_portfolio_volatility
            and portfolio_volatility > 0
        ):
            scale = self.config.target_portfolio_volatility / portfolio_volatility
            weights = {symbol: weight * scale for symbol, weight in weights.items()}
            vector *= scale
            portfolio_volatility *= scale
        final_cash = max(0.0, 1.0 - sum(weights.values()))
        weighted_asset_volatility = float(vector @ np.sqrt(np.clip(np.diag(covariance), 0.0, None)))
        diversification = (
            weighted_asset_volatility / portfolio_volatility if portfolio_volatility > 0 else 0.0
        )
        return OptimizationResult(weights, final_cash, portfolio_volatility, diversification)

    def _cap_and_normalize(
        self, raw: FloatArray, symbols: list[str], invested_target: float
    ) -> dict[str, float]:
        normalized = raw / raw.sum() * invested_target
        weights = dict(zip(symbols, normalized.tolist(), strict=True))
        for _ in range(len(symbols) + 1):
            excess = sum(
                max(0.0, weight - self.config.maximum_weight) for weight in weights.values()
            )
            if excess <= 1e-12:
                break
            uncapped = [
                symbol for symbol, weight in weights.items() if weight < self.config.maximum_weight
            ]
            for symbol in symbols:
                weights[symbol] = min(weights[symbol], self.config.maximum_weight)
            if not uncapped:
                break
            denominator = sum(weights[symbol] for symbol in uncapped)
            if denominator <= 0:
                increment = excess / len(uncapped)
                for symbol in uncapped:
                    weights[symbol] += increment
            else:
                for symbol in uncapped:
                    weights[symbol] += excess * weights[symbol] / denominator
        return {symbol: max(0.0, float(weight)) for symbol, weight in weights.items()}

    @staticmethod
    def _risk_parity(covariance: FloatArray, initial: FloatArray) -> FloatArray:
        weights = initial.copy()
        for _ in range(200):
            marginal = covariance @ weights
            total_variance = float(weights @ marginal)
            if total_variance <= 0:
                break
            contributions = weights * marginal / total_variance
            target = np.full(len(weights), 1.0 / len(weights))
            adjustment = np.divide(
                target,
                contributions,
                out=np.ones_like(target),
                where=contributions > 1e-12,
            )
            updated = weights * np.sqrt(adjustment)
            updated /= updated.sum()
            if float(np.max(np.abs(updated - weights))) < 1e-8:
                weights = updated
                break
            weights = updated
        return weights
