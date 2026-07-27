from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.atlas.portfolio.analytics import (
    AnalyticsConfig,
    diversification_statistics,
    performance_statistics,
    sanitize_returns,
)


@dataclass(frozen=True)
class InstitutionalConfig:
    minimum_price: float = 3.0
    minimum_market_cap: float = 100_000_000.0
    minimum_liquidity_score: float = 50.0
    minimum_data_quality_score: float = 80.0
    maximum_pair_correlation: float = 0.85
    minimum_history_observations: int = 60
    maximum_absolute_daily_return: float = 0.50
    spread_bps: float = 5.0
    slippage_bps: float = 8.0
    market_impact_bps: float = 5.0
    minimum_trade_value: float = 25.0
    monte_carlo_paths: int = 5000
    monte_carlo_days: int = 252
    bootstrap_block_size: int = 5
    random_seed: int = 42


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _history_path(directory: Path, asset_id: str) -> Path:
    return directory / f"{asset_id.replace(':', '__')}.csv"


def _price_series(frame: pd.DataFrame, name: str | None = None) -> pd.Series:
    date_column = next(
        (column for column in ("date", "timestamp", "Date") if column in frame),
        None,
    )
    price_column = next(
        (column for column in ("close", "Close", "adj_close", "Adj Close") if column in frame),
        None,
    )
    if date_column is None or price_column is None:
        return pd.Series(dtype=float, name=name)
    dates = pd.DatetimeIndex(
        pd.to_datetime(frame[date_column], errors="coerce", utc=True)
    ).tz_convert(None)
    prices = pd.Series(
        pd.to_numeric(frame[price_column], errors="coerce").to_numpy(),
        index=dates,
        name=name,
    )
    prices = prices.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    return prices[~prices.index.duplicated(keep="last")]


def load_return_matrix(
    portfolio: dict[str, Any],
    history_directory: Path,
    maximum_absolute_daily_return: float = 0.50,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, int]]:
    series: list[pd.Series] = []
    observations: dict[str, int] = {}
    clipped_observations: dict[str, int] = {}
    for row in portfolio.get("positions", []):
        asset_id = str(row["asset_id"])
        path = _history_path(history_directory, asset_id)
        if not path.exists():
            observations[asset_id] = 0
            clipped_observations[asset_id] = 0
            continue
        prices = _price_series(pd.read_csv(path), asset_id)
        raw_returns = prices.pct_change(fill_method=None).dropna()
        valid_raw = pd.to_numeric(raw_returns, errors="coerce").dropna()
        clipped_observations[asset_id] = int(
            (valid_raw.abs() > maximum_absolute_daily_return).sum()
        )
        returns = sanitize_returns(valid_raw, maximum_absolute_daily_return)
        observations[asset_id] = len(returns)
        if len(returns):
            series.append(returns)
    matrix = pd.concat(series, axis=1).sort_index() if series else pd.DataFrame()
    return matrix, observations, clipped_observations


def _optional_float(value: Any) -> float | None:
    """Coerce a scalar to float without exposing pandas overloads to MyPy."""
    if value is None:
        return None
    try:
        result = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _eligibility_rows(
    positions: pd.DataFrame,
    features: pd.DataFrame,
    metadata: pd.DataFrame,
    cfg: InstitutionalConfig,
) -> list[dict[str, Any]]:
    universe = positions.merge(
        features,
        on="asset_id",
        how="left",
        suffixes=("", "_feature"),
    )
    metadata_columns = [
        column for column in metadata.columns if column in {"asset_id", "market_cap", "status"}
    ]
    if metadata_columns:
        universe = universe.merge(
            metadata[metadata_columns],
            on="asset_id",
            how="left",
            suffixes=("", "_meta"),
        )

    result: list[dict[str, Any]] = []
    for row in universe.to_dict("records"):
        reasons: list[str] = []
        asset_class = str(row.get("asset_class", "stock"))
        price = _optional_float(row.get("price", row.get("close")))
        market_cap = _optional_float(row.get("market_cap", row.get("market_cap_meta")))
        liquidity = _optional_float(row.get("liquidity_score"))
        quality = _optional_float(row.get("data_quality_score"))
        if asset_class == "stock" and (price is None or price < cfg.minimum_price):
            reasons.append("price_below_minimum")
        if asset_class == "stock" and (market_cap is None or market_cap < cfg.minimum_market_cap):
            reasons.append("market_cap_below_minimum_or_missing")
        if liquidity is None or liquidity < cfg.minimum_liquidity_score:
            reasons.append("liquidity_below_minimum_or_missing")
        if quality is None or quality < cfg.minimum_data_quality_score:
            reasons.append("data_quality_below_minimum_or_missing")
        result.append(
            {
                "asset_id": row.get("asset_id"),
                "symbol": row.get("symbol"),
                "eligible": not reasons,
                "reasons": reasons,
            }
        )
    return result


def _benchmark_returns(
    benchmark_path: Path,
    maximum_absolute_daily_return: float,
) -> pd.Series | None:
    if not benchmark_path.exists():
        return None
    prices = _price_series(pd.read_csv(benchmark_path), "benchmark")
    if prices.empty:
        return None
    returns = prices.pct_change(fill_method=None).dropna()
    return sanitize_returns(returns, maximum_absolute_daily_return)


def _risk_contribution(
    covariance: pd.DataFrame,
    weights: pd.Series,
) -> list[dict[str, Any]]:
    if covariance.empty or weights.empty:
        return []
    assets = list(weights.index)
    matrix = covariance.reindex(index=assets, columns=assets).fillna(0.0).to_numpy()
    vector = weights.to_numpy(dtype=float)
    portfolio_variance = float(vector @ matrix @ vector)
    if portfolio_variance <= 0:
        return []
    component_variance = vector * (matrix @ vector)
    portfolio_volatility = math.sqrt(portfolio_variance)
    result: list[dict[str, Any]] = []
    for asset_id, value in zip(assets, component_variance, strict=True):
        result.append(
            {
                "asset_id": asset_id,
                "component_variance": float(value),
                "risk_contribution": float(value / portfolio_volatility),
                "risk_contribution_pct": float(value / portfolio_variance),
            }
        )
    return result


def _block_bootstrap(
    returns: np.ndarray,
    paths: int,
    days: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if len(returns) < block_size:
        return rng.choice(returns, size=(paths, days), replace=True)
    blocks_needed = math.ceil(days / block_size)
    max_start = len(returns) - block_size + 1
    starts = rng.integers(0, max_start, size=(paths, blocks_needed))
    result = np.empty((paths, blocks_needed * block_size), dtype=float)
    offsets = np.arange(block_size)
    for path_index in range(paths):
        result[path_index] = returns[(starts[path_index, :, None] + offsets).ravel()]
    return result[:, :days]


def _monte_carlo(
    returns: pd.Series,
    cfg: InstitutionalConfig,
) -> dict[str, Any]:
    if len(returns) < cfg.minimum_history_observations:
        return {"available": False, "paths": 0}
    clean = sanitize_returns(returns, cfg.maximum_absolute_daily_return)
    rng = np.random.default_rng(cfg.random_seed)
    simulations = _block_bootstrap(
        clean.to_numpy(dtype=float),
        cfg.monte_carlo_paths,
        cfg.monte_carlo_days,
        cfg.bootstrap_block_size,
        rng,
    )
    paths = np.cumprod(1.0 + simulations, axis=1)
    terminal = paths[:, -1] - 1.0
    drawdowns = paths / np.maximum.accumulate(paths, axis=1) - 1.0
    maximum_drawdowns = np.min(drawdowns, axis=1)
    return {
        "available": True,
        "paths": cfg.monte_carlo_paths,
        "days": cfg.monte_carlo_days,
        "bootstrap_block_size": cfg.bootstrap_block_size,
        "probability_of_loss": float(np.mean(terminal < 0)),
        "median_return": float(np.median(terminal)),
        "return_p05": float(np.quantile(terminal, 0.05)),
        "return_p95": float(np.quantile(terminal, 0.95)),
        "median_max_drawdown": float(np.median(maximum_drawdowns)),
        "worst_drawdown_p05": float(np.quantile(maximum_drawdowns, 0.05)),
        "random_seed": cfg.random_seed,
    }


def run_institutional_analysis(
    portfolio_path: Path,
    orders_path: Path,
    features_path: Path,
    metadata_path: Path,
    history_directory: Path,
    benchmark_path: Path,
    output_directory: Path,
    config: InstitutionalConfig | None = None,
) -> dict[str, Any]:
    cfg = config or InstitutionalConfig()
    portfolio = _read_json(portfolio_path)
    orders = _read_json(orders_path)
    positions = pd.DataFrame(portfolio.get("positions", []))
    features = pd.read_csv(features_path) if features_path.exists() else pd.DataFrame()
    metadata = pd.read_csv(metadata_path) if metadata_path.exists() else pd.DataFrame()
    eligibility_rows = _eligibility_rows(positions, features, metadata, cfg)

    returns, observations, clipped_observations = load_return_matrix(
        portfolio,
        history_directory,
        cfg.maximum_absolute_daily_return,
    )
    weights = (
        positions.set_index("asset_id")["target_weight"].astype(float)
        if not positions.empty
        else pd.Series(dtype=float)
    )
    usable = [column for column in returns.columns if column in weights.index]
    returns = returns[usable]
    aligned_weights = weights.reindex(usable).fillna(0.0)
    if float(aligned_weights.sum()) > 0:
        aligned_weights /= float(aligned_weights.sum())
    portfolio_returns = (
        returns.mul(aligned_weights, axis=1).sum(axis=1, min_count=1)
        if not returns.empty
        else pd.Series(dtype=float)
    )
    portfolio_returns = sanitize_returns(
        portfolio_returns,
        cfg.maximum_absolute_daily_return,
    )
    correlations = (
        returns.corr(min_periods=cfg.minimum_history_observations)
        if not returns.empty
        else pd.DataFrame()
    )
    covariance = (
        returns.cov(min_periods=cfg.minimum_history_observations) * 252
        if not returns.empty
        else pd.DataFrame()
    )

    analytics_config = AnalyticsConfig(
        minimum_observations=cfg.minimum_history_observations,
        maximum_absolute_daily_return=cfg.maximum_absolute_daily_return,
    )
    analytics = performance_statistics(
        portfolio_returns,
        _benchmark_returns(
            benchmark_path,
            cfg.maximum_absolute_daily_return,
        ),
        analytics_config,
    )
    diversification = diversification_statistics(weights, correlations)

    high_correlation_pairs: list[dict[str, Any]] = []
    if not correlations.empty:
        columns = list(correlations.columns)
        for index, left in enumerate(columns):
            for right in columns[index + 1 :]:
                value = _optional_float(correlations.at[left, right])
                if value is not None and value > cfg.maximum_pair_correlation:
                    high_correlation_pairs.append(
                        {"left": left, "right": right, "correlation": value}
                    )

    transaction_rows: list[dict[str, Any]] = []
    total_cost = 0.0
    cost_bps = cfg.spread_bps + cfg.slippage_bps + cfg.market_impact_bps
    for order in orders.get("orders", []):
        trade_value = abs(float(order.get("trade_value", 0.0)))
        estimated_cost = trade_value * cost_bps / 10_000.0
        accepted = trade_value >= cfg.minimum_trade_value
        if accepted:
            total_cost += estimated_cost
        transaction_rows.append(
            {
                "asset_id": order.get("asset_id"),
                "action": order.get("action"),
                "trade_value": trade_value,
                "estimated_cost": estimated_cost,
                "cost_bps": cost_bps,
                "accepted": accepted,
                "rejection_reason": None if accepted else "below_minimum_trade_value",
            }
        )

    stock_weight = float(weights[[item.startswith("stock:") for item in weights.index]].sum())
    crypto_weight = float(weights[[item.startswith("crypto:") for item in weights.index]].sum())
    technology_weight = 0.0
    healthcare_weight = 0.0
    if "sector" in positions:
        technology_weight = float(
            positions.loc[
                positions["sector"] == "Technology",
                "target_weight",
            ].sum()
        )
        healthcare_weight = float(
            positions.loc[
                positions["sector"] == "Healthcare",
                "target_weight",
            ].sum()
        )
    annual_volatility = float(analytics.get("annual_volatility") or 0.0)
    stress = {
        "equity_crash": -0.35 * stock_weight,
        "crypto_crash": -0.60 * crypto_weight,
        "technology_shock": -0.30 * technology_weight,
        "healthcare_shock": -0.25 * healthcare_weight,
        "correlation_convergence": -min(1.5 * annual_volatility, 0.75),
    }

    eligibility_coverage = (
        sum(bool(row["eligible"]) for row in eligibility_rows) / len(eligibility_rows)
        if eligibility_rows
        else 0.0
    )
    history_coverage = (
        sum(count >= cfg.minimum_history_observations for count in observations.values())
        / len(observations)
        if observations
        else 0.0
    )
    blockers: list[str] = []
    if eligibility_coverage < 0.90:
        blockers.append("eligibility_coverage_below_90_percent")
    if history_coverage < 0.90:
        blockers.append("history_coverage_below_90_percent")
    if high_correlation_pairs:
        blockers.append("high_correlation_pairs_detected")
    if analytics.get("annual_return") is None:
        blockers.append("analytics_unavailable")

    normalized_entropy = float(diversification.get("normalized_entropy") or 0.0)
    score = round(
        100
        * (
            0.35 * eligibility_coverage
            + 0.25 * history_coverage
            + 0.20 * normalized_entropy
            + 0.20 * (1.0 if not high_correlation_pairs else 0.5)
        )
    )
    status = "BACKTEST_READY" if not blockers else "RESEARCH_READY"
    config_hash = hashlib.sha256(
        json.dumps(asdict(cfg), sort_keys=True).encode("utf-8")
    ).hexdigest()

    artifacts: dict[str, Any] = {
        "eligibility_report": {
            "coverage": eligibility_coverage,
            "positions": eligibility_rows,
        },
        "correlation_report": {
            "threshold": cfg.maximum_pair_correlation,
            "high_correlation_pairs": high_correlation_pairs,
            "observations": observations,
            "clipped_return_observations": clipped_observations,
        },
        "optimizer_report": {
            "method": "constrained_hybrid",
            "eligibility_integrated_in_portfolio_engine": True,
            "note": "Only eligible candidates should enter the constrained allocator.",
        },
        "risk_contribution": {"positions": _risk_contribution(covariance, aligned_weights)},
        "transaction_cost_report": {
            "total_estimated_cost": total_cost,
            "cost_bps": cost_bps,
            "orders": transaction_rows,
        },
        "stress_test_report": {"scenario_returns": stress},
        "monte_carlo_report": _monte_carlo(portfolio_returns, cfg),
        "portfolio_intelligence": {
            "performance": analytics,
            "diversification": diversification,
            "return_sanitization_limit": cfg.maximum_absolute_daily_return,
        },
        "decision_ledger": {
            "run_id": config_hash[:16],
            "configuration_fingerprint": config_hash,
            "paper_only": True,
            "decisions": eligibility_rows,
        },
        "constraint_report": {
            "high_correlation_pair_count": len(high_correlation_pairs),
            "eligibility_coverage": eligibility_coverage,
            "history_coverage": history_coverage,
        },
        "readiness_report": {
            "status": status,
            "score": score,
            "blockers": blockers,
            "paper_only": True,
            "live_trading_enabled": False,
        },
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        output_path = output_directory / f"{name}.json"
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    correlations.to_csv(output_directory / "correlation_matrix.csv")
    covariance.to_csv(output_directory / "covariance_matrix.csv")
    return {
        "complete": True,
        "paper_only": True,
        "readiness": status,
        "score": score,
        "blockers": blockers,
        "output": str(output_directory),
    }
