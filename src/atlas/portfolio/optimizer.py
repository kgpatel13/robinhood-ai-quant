from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import OptimizeResult, minimize
from scipy.spatial.distance import squareform

from src.atlas.portfolio.analytics import (
    AnalyticsConfig,
    diversification_statistics,
    performance_statistics,
    sanitize_returns,
)
from src.atlas.portfolio.core import (
    CurrentPosition,
    PortfolioCandidate,
    PortfolioConfig,
    confidence_rank,
    normalize_weights,
)
from src.atlas.portfolio.institutional import load_return_matrix


@dataclass(frozen=True)
class OptimizerConfig:
    methods: tuple[str, ...] = (
        "equal",
        "score",
        "inverse_volatility",
        "hybrid",
        "risk_parity",
        "minimum_variance",
        "maximum_diversification",
        "hrp",
    )
    objective: str = "balanced"
    maximum_pair_correlation: float = 0.85
    candidate_buffer: int = 75
    minimum_history_observations: int = 60
    maximum_absolute_daily_return: float = 0.50
    transaction_cost_bps: float = 18.0
    correlation_penalty: float = 0.25

    def __post_init__(self) -> None:
        supported = {
            "equal",
            "score",
            "inverse_volatility",
            "hybrid",
            "risk_parity",
            "minimum_variance",
            "maximum_diversification",
            "hrp",
        }
        unknown = set(self.methods) - supported
        if unknown:
            raise ValueError(f"Unsupported optimizer methods: {sorted(unknown)}")
        if self.objective not in {"balanced", "sharpe", "diversification", "volatility"}:
            raise ValueError("Unsupported optimizer objective")
        if self.candidate_buffer < 1:
            raise ValueError("candidate_buffer must be positive")


@dataclass(frozen=True)
class ReplacementDecision:
    selected_asset_id: str
    selected_symbol: str
    source_rank: int
    composite_score: float
    diversification_benefit: float
    maximum_selected_correlation: float | None
    reason: str


@dataclass(frozen=True)
class ConstraintViolation:
    constraint: str
    actual: float
    limit: float
    passed: bool
    details: str


@dataclass(frozen=True)
class OptimizationResult:
    method: str
    weights: Mapping[str, float]
    metrics: Mapping[str, float | int | None]
    diversification: Mapping[str, float]
    constraint_violations: tuple[ConstraintViolation, ...]
    estimated_turnover: float
    estimated_transaction_cost: float
    score: float
    success: bool
    message: str


@dataclass(frozen=True)
class OptimizerSuiteResult:
    selected_method: str
    selected_assets: tuple[str, ...]
    methods: tuple[OptimizationResult, ...]
    replacements: tuple[ReplacementDecision, ...]
    explainability: Mapping[str, Mapping[str, Any]]


FloatArray = NDArray[np.float64]


class WeightingStrategy(Protocol):
    def __call__(
        self,
        candidates: Sequence[PortfolioCandidate],
        returns: pd.DataFrame,
    ) -> FloatArray: ...


def _eligible(candidate: PortfolioCandidate, config: PortfolioConfig) -> tuple[bool, str]:
    if not candidate.asset_id or not candidate.symbol.strip():
        return False, "invalid_identity"
    if candidate.asset_class.lower() not in {"stock", "crypto"}:
        return False, "unsupported_asset_class"
    if candidate.alpha_percentile < config.minimum_alpha_percentile:
        return False, "below_minimum_alpha_percentile"
    if confidence_rank(candidate.confidence) < confidence_rank(config.minimum_confidence):
        return False, "below_minimum_confidence"
    if not config.enforce_institutional_eligibility:
        return True, "eligible"
    if candidate.asset_class.lower() == "stock":
        if candidate.price is None or candidate.price < config.minimum_price:
            return False, "price_below_minimum"
        if candidate.market_cap is None or candidate.market_cap < config.minimum_market_cap:
            return False, "market_cap_below_minimum_or_missing"
    if (
        candidate.liquidity_score is None
        or candidate.liquidity_score < config.minimum_liquidity_score
    ):
        return False, "liquidity_below_minimum_or_missing"
    if (
        candidate.data_quality_score is None
        or candidate.data_quality_score < config.minimum_data_quality_score
    ):
        return False, "data_quality_below_minimum_or_missing"
    return True, "eligible"


def _confidence_value(value: str) -> float:
    return {"low": 0.25, "medium": 0.65, "high": 1.0}.get(value.lower(), 0.0)


def _candidate_base_score(candidate: PortfolioCandidate) -> float:
    liquidity = (candidate.liquidity_score or 0.0) / 100.0
    volatility = candidate.volatility_60d
    volatility_quality = 1.0 / (1.0 + max(volatility or 1.0, 0.0))
    return (
        0.40 * max(candidate.alpha_percentile, 0.0)
        + 0.25 * _confidence_value(candidate.confidence)
        + 0.15 * liquidity
        + 0.10 * volatility_quality
    )


def select_correlation_aware_candidates(
    candidates: Sequence[PortfolioCandidate],
    return_matrix: pd.DataFrame,
    portfolio_config: PortfolioConfig,
    optimizer_config: OptimizerConfig,
) -> tuple[list[PortfolioCandidate], list[ReplacementDecision], dict[str, str]]:
    excluded: dict[str, str] = {}
    pool: list[PortfolioCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.rank, item.asset_id)):
        allowed, reason = _eligible(candidate, portfolio_config)
        if not allowed:
            excluded[candidate.asset_id or f"invalid:{candidate.rank}"] = reason
            continue
        pool.append(candidate)
        if len(pool) >= optimizer_config.candidate_buffer:
            break

    correlations = return_matrix.corr(
        min_periods=optimizer_config.minimum_history_observations
    )
    selected: list[PortfolioCandidate] = []
    decisions: list[ReplacementDecision] = []
    remaining = list(pool)
    while remaining and len(selected) < portfolio_config.max_positions:
        best: PortfolioCandidate | None = None
        best_score = -math.inf
        best_max_corr: float | None = None
        best_benefit = 1.0
        for candidate in remaining:
            correlations_to_selected: list[float] = []
            if candidate.asset_id in correlations.index:
                for existing in selected:
                    if existing.asset_id in correlations.columns:
                        value = correlations.at[candidate.asset_id, existing.asset_id]
                        if pd.notna(value):
                            correlation_value = float(
                                np.asarray(value, dtype=float).item()
                            )
                            correlations_to_selected.append(abs(correlation_value))
            max_corr = max(correlations_to_selected, default=None)
            average_corr = (
                float(np.mean(correlations_to_selected))
                if correlations_to_selected
                else 0.0
            )
            diversification_benefit = max(1.0 - average_corr, 0.0)
            score = _candidate_base_score(candidate) + 0.10 * diversification_benefit
            if max_corr is not None and max_corr > optimizer_config.maximum_pair_correlation:
                score -= optimizer_config.correlation_penalty * (
                    max_corr - optimizer_config.maximum_pair_correlation
                )
            if score > best_score or (
                math.isclose(score, best_score) and best is not None and candidate.rank < best.rank
            ):
                best = candidate
                best_score = score
                best_max_corr = max_corr
                best_benefit = diversification_benefit
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
        decisions.append(
            ReplacementDecision(
                selected_asset_id=best.asset_id,
                selected_symbol=best.symbol,
                source_rank=best.rank,
                composite_score=best_score,
                diversification_benefit=best_benefit,
                maximum_selected_correlation=best_max_corr,
                reason=(
                    "highest_constraint_eligible_correlation_adjusted_score"
                    if selected[:-1]
                    else "highest_constraint_eligible_base_score"
                ),
            )
        )
    return selected, decisions, excluded


def _safe_covariance(returns: pd.DataFrame) -> FloatArray:
    if returns.empty:
        return np.eye(0)
    covariance = returns.cov().to_numpy(dtype=float) * 252.0
    covariance = np.nan_to_num(covariance, nan=0.0, posinf=0.0, neginf=0.0)
    covariance = (covariance + covariance.T) / 2.0
    covariance += np.eye(len(covariance)) * 1e-8
    return covariance


def _volatility_vector(
    candidates: Sequence[PortfolioCandidate],
    returns: pd.DataFrame,
) -> FloatArray:
    historical = (
        returns.std(ddof=1).reindex([item.asset_id for item in candidates])
        * math.sqrt(252)
    )
    supplied = [item.volatility_60d for item in candidates]
    values: list[float] = []
    valid = [float(value) for value in historical.dropna() if float(value) > 0]
    fallback = float(np.median(valid)) if valid else 0.30
    for index, _candidate in enumerate(candidates):
        historical_value = historical.iloc[index] if index < len(historical) else np.nan
        if pd.notna(historical_value) and float(historical_value) > 0:
            values.append(float(historical_value))
        else:
            supplied_value = supplied[index]
            if supplied_value is not None and supplied_value > 0:
                values.append(float(supplied_value))
            else:
                values.append(fallback)
    return np.asarray(values, dtype=np.float64)


def _base_weights(
    method: str,
    candidates: Sequence[PortfolioCandidate],
    returns: pd.DataFrame,
) -> FloatArray:
    count = len(candidates)
    if count == 0:
        return np.asarray([], dtype=float)
    scores = np.asarray([max(item.alpha_percentile, 0.01) for item in candidates])
    volatility = _volatility_vector(candidates, returns)
    if method == "equal":
        return np.full(count, 1.0 / count)
    if method == "score":
        return np.asarray(normalize_weights(scores.tolist()), dtype=np.float64)
    if method == "inverse_volatility":
        raw = (1.0 / np.maximum(volatility, 0.01)).tolist()
        return np.asarray(normalize_weights(raw), dtype=np.float64)
    if method == "hybrid":
        raw = np.sqrt(scores / np.maximum(volatility, 0.01))
        return np.asarray(normalize_weights(raw.tolist()), dtype=np.float64)
    raise ValueError(f"Unsupported base method: {method}")


def _minimum_variance(covariance: FloatArray) -> tuple[FloatArray, bool, str]:
    count = len(covariance)
    initial = np.full(count, 1.0 / count)
    result: OptimizeResult = minimize(
        lambda weights: float(weights @ covariance @ weights),
        initial,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * count,
        constraints=[{"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)}],
        options={"maxiter": 1000, "ftol": 1e-12},
    )  # type: ignore[call-overload]
    return np.asarray(result.x, dtype=float), bool(result.success), str(result.message)


def _maximum_diversification(
    covariance: FloatArray,
) -> tuple[FloatArray, bool, str]:
    count = len(covariance)
    initial = np.full(count, 1.0 / count)
    asset_volatility = np.sqrt(np.maximum(np.diag(covariance), 1e-12))

    def objective(weights: np.ndarray) -> float:
        portfolio_volatility = math.sqrt(max(float(weights @ covariance @ weights), 1e-12))
        return -float(weights @ asset_volatility) / portfolio_volatility

    result: OptimizeResult = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * count,
        constraints=[{"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)}],
        options={"maxiter": 1000, "ftol": 1e-12},
    )  # type: ignore[call-overload]
    return np.asarray(result.x, dtype=float), bool(result.success), str(result.message)


def _risk_parity(covariance: FloatArray) -> tuple[FloatArray, bool, str]:
    count = len(covariance)
    initial = np.full(count, 1.0 / count)
    target = np.full(count, 1.0 / count)

    def objective(weights: np.ndarray) -> float:
        variance = max(float(weights @ covariance @ weights), 1e-12)
        marginal = covariance @ weights
        contribution = weights * marginal / variance
        return float(np.square(contribution - target).sum())

    result: OptimizeResult = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=[(1e-8, 1.0)] * count,
        constraints=[{"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)}],
        options={"maxiter": 2000, "ftol": 1e-12},
    )  # type: ignore[call-overload]
    return np.asarray(result.x, dtype=float), bool(result.success), str(result.message)


def _cluster_variance(covariance: FloatArray, indexes: Sequence[int]) -> float:
    subset = covariance[np.ix_(indexes, indexes)]
    inverse_variance = 1.0 / np.maximum(np.diag(subset), 1e-12)
    weights = inverse_variance / inverse_variance.sum()
    return float(weights @ subset @ weights)


def _hrp(covariance: FloatArray) -> tuple[FloatArray, bool, str]:
    count = len(covariance)
    if count <= 1:
        return np.ones(count), True, "single_asset"
    volatility = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    correlation = covariance / np.outer(volatility, volatility)
    correlation = np.clip(correlation, -1.0, 1.0)
    distance = np.sqrt(np.maximum((1.0 - correlation) / 2.0, 0.0))
    np.fill_diagonal(distance, 0.0)
    order = [
        int(index)
        for index in leaves_list(
            linkage(squareform(distance, checks=False), method="single")
        )
    ]
    weights = pd.Series(1.0, index=order, dtype=float)
    clusters: list[list[int]] = [order]
    while clusters:
        next_clusters: list[list[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            midpoint = len(cluster) // 2
            left, right = cluster[:midpoint], cluster[midpoint:]
            left_variance = _cluster_variance(covariance, left)
            right_variance = _cluster_variance(covariance, right)
            alpha = 1.0 - left_variance / max(left_variance + right_variance, 1e-12)
            weights.loc[left] *= alpha
            weights.loc[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters
    output = np.zeros(count, dtype=float)
    for index, value in weights.items():
        output[int(np.asarray(index).item())] = float(value)
    return output / output.sum(), True, "hierarchical_risk_parity"


def _project_constraints(
    weights: FloatArray,
    candidates: Sequence[PortfolioCandidate],
    config: PortfolioConfig,
) -> FloatArray:
    investable = 1.0 - config.cash_reserve_pct
    result = np.maximum(np.asarray(weights, dtype=float), 0.0)
    if result.sum() <= 0:
        result = np.ones(len(candidates), dtype=float)
    result = result / result.sum() * investable
    for _ in range(100):
        previous = result.copy()
        result = np.minimum(result, config.max_position_pct)
        crypto = np.asarray(
            [item.asset_class.lower() == "crypto" for item in candidates], dtype=bool
        )
        if result[crypto].sum() > config.max_crypto_pct:
            result[crypto] *= config.max_crypto_pct / result[crypto].sum()
        for attribute, limit in (
            ("sector", config.max_sector_pct),
            ("industry", config.max_industry_pct),
        ):
            groups: dict[str, list[int]] = defaultdict(list)
            for index, candidate in enumerate(candidates):
                value = getattr(candidate, attribute)
                if value:
                    groups[str(value).strip().lower()].append(index)
            for indexes in groups.values():
                total = result[indexes].sum()
                if total > limit:
                    result[indexes] *= limit / total
        shortfall = investable - result.sum()
        if shortfall > 1e-10:
            room = np.maximum(config.max_position_pct - result, 0.0)
            if crypto.any():
                crypto_room_total = max(config.max_crypto_pct - result[crypto].sum(), 0.0)
                crypto_room = room[crypto]
                if crypto_room.sum() > crypto_room_total and crypto_room.sum() > 0:
                    room[crypto] *= crypto_room_total / crypto_room.sum()
            if room.sum() > 0:
                result += np.minimum(shortfall * room / room.sum(), room)
        if np.max(np.abs(result - previous)) < 1e-10:
            break
    if result.sum() > investable and result.sum() > 0:
        result *= investable / result.sum()
    return np.asarray(result, dtype=np.float64)


def _validate_constraints(
    weights: np.ndarray,
    candidates: Sequence[PortfolioCandidate],
    config: PortfolioConfig,
) -> tuple[ConstraintViolation, ...]:
    rows: list[ConstraintViolation] = []
    largest = float(weights.max()) if len(weights) else 0.0
    rows.append(
        ConstraintViolation(
            "maximum_position_weight",
            largest,
            config.max_position_pct,
            largest <= config.max_position_pct + 1e-8,
            "largest target position",
        )
    )
    crypto = float(
        sum(weight for weight, item in zip(weights, candidates, strict=True)
            if item.asset_class.lower() == "crypto")
    )
    rows.append(
        ConstraintViolation(
            "maximum_crypto_weight",
            crypto,
            config.max_crypto_pct,
            crypto <= config.max_crypto_pct + 1e-8,
            "aggregate crypto target weight",
        )
    )
    for attribute, limit in (
        ("sector", config.max_sector_pct),
        ("industry", config.max_industry_pct),
    ):
        groups: dict[str, float] = defaultdict(float)
        for weight, candidate in zip(weights, candidates, strict=True):
            value = getattr(candidate, attribute)
            if value:
                groups[str(value)] += float(weight)
        actual = max(groups.values(), default=0.0)
        rows.append(
            ConstraintViolation(
                f"maximum_{attribute}_weight",
                actual,
                limit,
                actual <= limit + 1e-8,
                f"largest {attribute} allocation",
            )
        )
    invested = float(weights.sum())
    target = 1.0 - config.cash_reserve_pct
    rows.append(
        ConstraintViolation(
            "investable_weight",
            invested,
            target,
            abs(invested - target) <= 1e-6,
            "target invested weight after cash reserve",
        )
    )
    return tuple(rows)


def _turnover_and_cost(
    weights: np.ndarray,
    candidates: Sequence[PortfolioCandidate],
    current_positions: Sequence[CurrentPosition],
    config: PortfolioConfig,
    optimizer_config: OptimizerConfig,
) -> tuple[float, float]:
    current = {item.asset_id: item.market_value / config.capital for item in current_positions}
    target = {
        item.asset_id: float(weight)
        for item, weight in zip(candidates, weights, strict=True)
    }
    identifiers = set(current) | set(target)
    one_way_turnover = 0.5 * sum(
        abs(target.get(asset_id, 0.0) - current.get(asset_id, 0.0))
        for asset_id in identifiers
    )
    cost = one_way_turnover * config.capital * optimizer_config.transaction_cost_bps / 10_000.0
    return float(one_way_turnover), float(cost)


def _method_score(
    metrics: Mapping[str, float | int | None],
    diversification: Mapping[str, float],
    turnover: float,
    objective: str,
) -> float:
    sharpe = float(metrics.get("sharpe_ratio") or 0.0)
    volatility = float(metrics.get("annual_volatility") or 1.0)
    drawdown = abs(float(metrics.get("maximum_drawdown") or 1.0))
    effective = float(diversification.get("effective_positions", 0.0))
    if objective == "sharpe":
        return sharpe - 0.20 * turnover
    if objective == "diversification":
        return effective - 5.0 * turnover
    if objective == "volatility":
        return -volatility - 0.20 * turnover
    return sharpe + 0.03 * effective - 0.50 * drawdown - 0.25 * turnover


def _portfolio_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    if returns.empty or len(weights) == 0:
        return pd.Series(dtype=float)
    normalized = weights / max(weights.sum(), 1e-12)
    return returns.mul(normalized, axis=1).sum(axis=1, min_count=1)


def run_optimizer_suite(
    candidates: Sequence[PortfolioCandidate],
    history_directory: Path,
    portfolio_config: PortfolioConfig,
    optimizer_config: OptimizerConfig | None = None,
    current_positions: Sequence[CurrentPosition] = (),
    benchmark_returns: pd.Series | None = None,
) -> OptimizerSuiteResult:
    cfg = optimizer_config or OptimizerConfig()
    eligible_pool = [
        item for item in sorted(candidates, key=lambda row: (row.rank, row.asset_id))
        if _eligible(item, portfolio_config)[0]
    ][: cfg.candidate_buffer]
    provisional = {
        "positions": [{"asset_id": item.asset_id} for item in eligible_pool]
    }
    pool_returns, _, _ = load_return_matrix(
        provisional,
        history_directory,
        cfg.maximum_absolute_daily_return,
    )
    selected, replacements, _ = select_correlation_aware_candidates(
        candidates,
        pool_returns,
        portfolio_config,
        cfg,
    )
    selected_ids = [item.asset_id for item in selected]
    returns = pool_returns.reindex(columns=selected_ids)
    usable_columns = [
        column for column in returns.columns
        if int(returns[column].count()) >= cfg.minimum_history_observations
    ]
    if usable_columns:
        returns = returns[usable_columns]
        selected_by_id = {item.asset_id: item for item in selected}
        selected = [selected_by_id[column] for column in usable_columns]
    returns = returns.dropna(how="all")
    covariance = _safe_covariance(returns)
    correlation = returns.corr(min_periods=cfg.minimum_history_observations)
    analytics_config = AnalyticsConfig(
        minimum_observations=cfg.minimum_history_observations,
        maximum_absolute_daily_return=cfg.maximum_absolute_daily_return,
    )
    method_results: list[OptimizationResult] = []
    for method in cfg.methods:
        success = True
        message = "deterministic_weighting"
        if method in {"equal", "score", "inverse_volatility", "hybrid"}:
            raw_weights = _base_weights(method, selected, returns)
        elif method == "minimum_variance":
            raw_weights, success, message = _minimum_variance(covariance)
        elif method == "maximum_diversification":
            raw_weights, success, message = _maximum_diversification(covariance)
        elif method == "risk_parity":
            raw_weights, success, message = _risk_parity(covariance)
        elif method == "hrp":
            raw_weights, success, message = _hrp(covariance)
        else:
            raise RuntimeError(f"Unreachable optimizer method: {method}")
        weights = _project_constraints(raw_weights, selected, portfolio_config)
        violations = _validate_constraints(weights, selected, portfolio_config)
        success = success and all(item.passed for item in violations)
        portfolio_returns = sanitize_returns(
            _portfolio_returns(returns, weights),
            cfg.maximum_absolute_daily_return,
        )
        metrics = performance_statistics(
            portfolio_returns,
            benchmark_returns,
            analytics_config,
        )
        weight_series = pd.Series(
            weights,
            index=[item.asset_id for item in selected],
            dtype=float,
        )
        raw_diversification = diversification_statistics(weight_series, correlation)
        diversification: dict[str, float] = {
            key: float(value) if value is not None else 0.0
            for key, value in raw_diversification.items()
        }
        turnover, cost = _turnover_and_cost(
            weights,
            selected,
            current_positions,
            portfolio_config,
            cfg,
        )
        score = _method_score(metrics, diversification, turnover, cfg.objective)
        method_results.append(
            OptimizationResult(
                method=method,
                weights=dict(zip(weight_series.index, weights, strict=True)),
                metrics=metrics,
                diversification=diversification,
                constraint_violations=violations,
                estimated_turnover=turnover,
                estimated_transaction_cost=cost,
                score=score,
                success=success,
                message=message,
            )
        )
    successful = [item for item in method_results if item.success]
    selected_result = max(successful or method_results, key=lambda item: item.score)
    candidates_by_id = {item.asset_id: item for item in selected}
    explainability: dict[str, dict[str, Any]] = {}
    for asset_id, weight in selected_result.weights.items():
        candidate = candidates_by_id[asset_id]
        explainability[asset_id] = {
            "symbol": candidate.symbol,
            "source_rank": candidate.rank,
            "alpha_percentile": candidate.alpha_percentile,
            "confidence": candidate.confidence,
            "liquidity_score": candidate.liquidity_score,
            "data_quality_score": candidate.data_quality_score,
            "target_weight": weight,
            "optimizer_method": selected_result.method,
            "selection_reason": "eligible_and_correlation_aware_composite_rank",
            "allocation_reason": "selected_optimizer_constraint_projected_weight",
        }
    return OptimizerSuiteResult(
        selected_method=selected_result.method,
        selected_assets=tuple(item.asset_id for item in selected),
        methods=tuple(method_results),
        replacements=tuple(replacements),
        explainability=explainability,
    )


def write_optimizer_reports(result: OptimizerSuiteResult, output_directory: Path) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    method_payloads = []
    for item in result.methods:
        payload = asdict(item)
        method_payloads.append(payload)
    reports: dict[str, Any] = {
        "optimizer_comparison.json": {
            "selected_method": result.selected_method,
            "selected_assets": list(result.selected_assets),
            "methods": method_payloads,
        },
        "optimizer_constraints.json": {
            item.method: [asdict(row) for row in item.constraint_violations]
            for item in result.methods
        },
        "replacement_history.json": [asdict(item) for item in result.replacements],
        "optimizer_explainability.json": result.explainability,
        "optimizer_diagnostics.json": {
            "selected_method": result.selected_method,
            "successful_methods": [item.method for item in result.methods if item.success],
            "failed_methods": [item.method for item in result.methods if not item.success],
            "paper_only": True,
        },
    }
    artifacts: dict[str, str] = {}
    for filename, payload in reports.items():
        path = output_directory / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        artifacts[path.stem] = str(path)
    return artifacts
