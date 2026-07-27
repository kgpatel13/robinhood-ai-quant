from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.atlas.portfolio.analytics import (
    AnalyticsConfig,
    performance_statistics,
    sanitize_returns,
)
from src.atlas.portfolio.core import PortfolioCandidate, PortfolioConfig
from src.atlas.portfolio.institutional import load_return_matrix
from src.atlas.portfolio.optimizer import (
    OptimizerConfig,
    _base_weights,
    _hrp,
    _maximum_diversification,
    _minimum_variance,
    _portfolio_returns,
    _project_constraints,
    _risk_parity,
    _safe_covariance,
    _validate_constraints,
    select_correlation_aware_candidates,
)


@dataclass(frozen=True)
class WalkForwardConfig:
    training_observations: int = 252
    testing_observations: int = 63
    step_observations: int = 63
    minimum_windows: int = 2
    method: str = "auto"
    transaction_cost_bps: float = 18.0
    maximum_absolute_daily_return: float = 0.50
    annualization_factor: int = 252
    regime_lookback: int = 63

    def __post_init__(self) -> None:
        supported = {
            "auto",
            "equal",
            "score",
            "inverse_volatility",
            "hybrid",
            "risk_parity",
            "minimum_variance",
            "maximum_diversification",
            "hrp",
        }
        if self.method not in supported:
            raise ValueError(f"Unsupported walk-forward method: {self.method}")
        for name, value in (
            ("training_observations", self.training_observations),
            ("testing_observations", self.testing_observations),
            ("step_observations", self.step_observations),
            ("minimum_windows", self.minimum_windows),
            ("annualization_factor", self.annualization_factor),
            ("regime_lookback", self.regime_lookback),
        ):
            if value < 1:
                raise ValueError(f"{name} must be positive")
        if self.transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")


@dataclass(frozen=True)
class ReplayWindow:
    window: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    method: str
    observation_count: int
    turnover: float
    transaction_cost: float
    gross_return: float
    net_return: float
    annual_return: float | None
    annual_volatility: float | None
    sharpe_ratio: float | None
    maximum_drawdown: float | None
    regime: str
    constraints_passed: bool
    weights: dict[str, float]


@dataclass(frozen=True)
class WalkForwardResult:
    windows: tuple[ReplayWindow, ...]
    daily_returns: pd.Series
    gross_daily_returns: pd.Series
    attribution: pd.DataFrame
    summary: dict[str, Any]
    regime_summary: dict[str, dict[str, float | int | None]]
    diagnostics: dict[str, Any]


def _weights_for_method(
    method: str,
    selected: list[PortfolioCandidate],
    training_returns: pd.DataFrame,
    portfolio_config: PortfolioConfig,
) -> np.ndarray:
    covariance = _safe_covariance(training_returns)
    if method in {"equal", "score", "inverse_volatility", "hybrid"}:
        raw = _base_weights(method, selected, training_returns)
    elif method == "minimum_variance":
        raw, _, _ = _minimum_variance(covariance)
    elif method == "maximum_diversification":
        raw, _, _ = _maximum_diversification(covariance)
    elif method == "risk_parity":
        raw, _, _ = _risk_parity(covariance)
    elif method == "hrp":
        raw, _, _ = _hrp(covariance)
    else:
        raise ValueError(f"Unsupported method: {method}")
    return _project_constraints(raw, selected, portfolio_config)


def _training_score(returns: pd.Series, annualization_factor: int) -> float:
    clean = returns.dropna()
    if len(clean) < 2:
        return -math.inf
    volatility = float(clean.std(ddof=1)) * math.sqrt(annualization_factor)
    if volatility <= 0:
        return -math.inf
    annual_return = float(clean.mean()) * annualization_factor
    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    maximum_drawdown = abs(float(drawdown.min()))
    return annual_return / volatility - 0.50 * maximum_drawdown


def _choose_method(
    requested_method: str,
    methods: tuple[str, ...],
    selected: list[PortfolioCandidate],
    training_returns: pd.DataFrame,
    portfolio_config: PortfolioConfig,
    annualization_factor: int,
) -> tuple[str, np.ndarray]:
    if requested_method != "auto":
        return requested_method, _weights_for_method(
            requested_method,
            selected,
            training_returns,
            portfolio_config,
        )
    best_method = methods[0]
    best_weights = _weights_for_method(
        best_method,
        selected,
        training_returns,
        portfolio_config,
    )
    best_score = _training_score(
        _portfolio_returns(training_returns, best_weights),
        annualization_factor,
    )
    for method in methods[1:]:
        weights = _weights_for_method(
            method,
            selected,
            training_returns,
            portfolio_config,
        )
        score = _training_score(
            _portfolio_returns(training_returns, weights),
            annualization_factor,
        )
        if score > best_score:
            best_method = method
            best_weights = weights
            best_score = score
    return best_method, best_weights


def _turnover(previous: dict[str, float], current: dict[str, float]) -> float:
    assets = set(previous) | set(current)
    return 0.5 * sum(abs(current.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in assets)


def _regime(series: pd.Series, annualization_factor: int) -> str:
    clean = series.dropna()
    if len(clean) < 2:
        return "insufficient_history"
    annual_return = float(clean.mean()) * annualization_factor
    annual_volatility = float(clean.std(ddof=1)) * math.sqrt(annualization_factor)
    if annual_volatility >= 0.30:
        return "high_volatility"
    if annual_return >= 0.10:
        return "risk_on"
    if annual_return <= -0.10:
        return "risk_off"
    return "neutral"


def _compound_return(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return 0.0
    values = clean.to_numpy(dtype=np.float64, copy=False)
    return float(np.prod(1.0 + values, dtype=np.float64) - 1.0)


def run_walk_forward(
    candidates: list[PortfolioCandidate],
    history_directory: Path,
    portfolio_config: PortfolioConfig,
    optimizer_config: OptimizerConfig | None = None,
    walk_forward_config: WalkForwardConfig | None = None,
) -> WalkForwardResult:
    opt_cfg = optimizer_config or OptimizerConfig()
    cfg = walk_forward_config or WalkForwardConfig()
    provisional = {"positions": [{"asset_id": item.asset_id} for item in candidates]}
    full_returns, missing_assets, history_diagnostics = load_return_matrix(
        provisional,
        history_directory,
        cfg.maximum_absolute_daily_return,
    )
    full_returns = full_returns.sort_index().dropna(how="all")
    selected, replacements, excluded = select_correlation_aware_candidates(
        candidates,
        full_returns,
        portfolio_config,
        opt_cfg,
    )
    selected_by_id = {item.asset_id: item for item in selected}
    selected_ids = [item.asset_id for item in selected]
    full_returns = full_returns.reindex(columns=selected_ids)
    required = cfg.training_observations + cfg.testing_observations
    if len(full_returns) < required:
        raise ValueError(
            f"Insufficient history: need at least {required} observations, "
            f"found {len(full_returns)}"
        )

    windows: list[ReplayWindow] = []
    net_parts: list[pd.Series] = []
    gross_parts: list[pd.Series] = []
    attribution_parts: list[pd.DataFrame] = []
    previous_weights: dict[str, float] = {}
    start = 0
    window_number = 1
    analytics_config = AnalyticsConfig(
        periods_per_year=cfg.annualization_factor,
        minimum_observations=max(2, min(20, cfg.testing_observations)),
        maximum_absolute_daily_return=cfg.maximum_absolute_daily_return,
    )
    while start + required <= len(full_returns):
        train = full_returns.iloc[start : start + cfg.training_observations]
        test_start = start + cfg.training_observations
        test = full_returns.iloc[test_start : test_start + cfg.testing_observations]
        usable = [
            column
            for column in train.columns
            if int(train[column].count()) >= opt_cfg.minimum_history_observations
            and int(test[column].count()) > 0
        ]
        if not usable:
            start += cfg.step_observations
            continue
        window_selected = [selected_by_id[column] for column in usable]
        train = train[usable]
        test = test[usable]
        method, weights_array = _choose_method(
            cfg.method,
            opt_cfg.methods,
            window_selected,
            train,
            portfolio_config,
            cfg.annualization_factor,
        )
        weights = dict(zip(usable, (float(value) for value in weights_array), strict=True))
        violations = _validate_constraints(weights_array, window_selected, portfolio_config)
        constraints_passed = all(item.passed for item in violations)
        gross = sanitize_returns(
            _portfolio_returns(test, weights_array),
            cfg.maximum_absolute_daily_return,
        )
        turnover = _turnover(previous_weights, weights)
        transaction_cost = turnover * cfg.transaction_cost_bps / 10_000.0
        net = gross.copy()
        if not net.empty:
            net.iloc[0] = float(net.iloc[0]) - transaction_cost
        metrics = performance_statistics(net, None, analytics_config)
        regime_history = full_returns.iloc[
            max(0, test_start - cfg.regime_lookback) : test_start
        ].mean(axis=1)
        regime = _regime(regime_history, cfg.annualization_factor)
        attribution = test.mul(weights_array, axis=1)
        attribution["window"] = window_number
        attribution["date"] = attribution.index.astype(str)
        attribution_parts.append(attribution.reset_index(drop=True))
        gross_parts.append(gross)
        net_parts.append(net)
        windows.append(
            ReplayWindow(
                window=window_number,
                train_start=str(train.index[0]),
                train_end=str(train.index[-1]),
                test_start=str(test.index[0]),
                test_end=str(test.index[-1]),
                method=method,
                observation_count=int(net.count()),
                turnover=turnover,
                transaction_cost=transaction_cost,
                gross_return=_compound_return(gross),
                net_return=_compound_return(net),
                annual_return=metrics.get("annual_return"),
                annual_volatility=metrics.get("annual_volatility"),
                sharpe_ratio=metrics.get("sharpe_ratio"),
                maximum_drawdown=metrics.get("maximum_drawdown"),
                regime=regime,
                constraints_passed=constraints_passed,
                weights=weights,
            )
        )
        previous_weights = weights
        window_number += 1
        start += cfg.step_observations

    if len(windows) < cfg.minimum_windows:
        raise ValueError(
            f"Walk-forward produced {len(windows)} windows; "
            f"minimum required is {cfg.minimum_windows}"
        )
    gross_daily = pd.concat(gross_parts).sort_index()
    daily = pd.concat(net_parts).sort_index()
    combined_metrics = performance_statistics(daily, None, analytics_config)
    regime_summary: dict[str, dict[str, float | int | None]] = {}
    for regime_name in sorted({window.regime for window in windows}):
        regime_windows = [window for window in windows if window.regime == regime_name]
        regime_summary[regime_name] = {
            "window_count": len(regime_windows),
            "average_net_return": float(np.mean([item.net_return for item in regime_windows])),
            "average_turnover": float(np.mean([item.turnover for item in regime_windows])),
            "average_sharpe": float(
                np.mean([
                    item.sharpe_ratio
                    for item in regime_windows
                    if item.sharpe_ratio is not None
                ])
            ) if any(item.sharpe_ratio is not None for item in regime_windows) else None,
        }
    summary: dict[str, Any] = {
        **combined_metrics,
        "window_count": len(windows),
        "gross_compound_return": _compound_return(gross_daily),
        "net_compound_return": _compound_return(daily),
        "total_transaction_cost": float(sum(item.transaction_cost for item in windows)),
        "average_turnover": float(np.mean([item.turnover for item in windows])),
        "method_counts": {
            method: sum(1 for item in windows if item.method == method)
            for method in sorted({item.method for item in windows})
        },
        "all_constraints_passed": all(item.constraints_passed for item in windows),
    }
    attribution_frame = pd.concat(attribution_parts, ignore_index=True)
    diagnostics = {
        "paper_only": True,
        "lookahead_control": "train_window_only_weights_test_window_only_evaluation",
        "candidate_universe_limitation": (
            "candidate ranking is supplied as a static input; historical point-in-time "
            "rank snapshots are required to eliminate universe-selection lookahead"
        ),
        "missing_assets": missing_assets,
        "history_diagnostics": history_diagnostics,
        "replacement_count": len(replacements),
        "excluded_count": len(excluded),
        "selected_asset_count": len(selected),
    }
    return WalkForwardResult(
        windows=tuple(windows),
        daily_returns=daily,
        gross_daily_returns=gross_daily,
        attribution=attribution_frame,
        summary=summary,
        regime_summary=regime_summary,
        diagnostics=diagnostics,
    )


def write_walk_forward_reports(
    result: WalkForwardResult,
    output_directory: Path,
) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {
        "walk_forward_summary.json": result.summary,
        "walk_forward_windows.json": [asdict(window) for window in result.windows],
        "regime_summary.json": result.regime_summary,
        "walk_forward_diagnostics.json": result.diagnostics,
    }
    artifacts: dict[str, str] = {}
    for filename, payload in reports.items():
        path = output_directory / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        artifacts[path.stem] = str(path)
    returns_path = output_directory / "walk_forward_returns.csv"
    pd.DataFrame(
        {
            "date": result.daily_returns.index.astype(str),
            "gross_return": result.gross_daily_returns.to_numpy(),
            "net_return": result.daily_returns.to_numpy(),
        }
    ).to_csv(returns_path, index=False)
    artifacts[returns_path.stem] = str(returns_path)
    attribution_path = output_directory / "performance_attribution.csv"
    result.attribution.to_csv(attribution_path, index=False)
    artifacts[attribution_path.stem] = str(attribution_path)
    return artifacts
