from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any, cast

import numpy as np
import pandas as pd

from src.atlas.portfolio.core import TargetPosition


@dataclass(frozen=True)
class AnalyticsConfig:
    risk_free_rate: float = 0.04
    confidence_level: float = 0.95
    periods_per_year: int = 252
    minimum_observations: int = 60
    maximum_absolute_daily_return: float = 0.50
    benchmark_symbol: str = "SPY"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_level < 1.0:
            raise ValueError("confidence_level must be within [0, 1)")
        if self.minimum_observations < 2:
            raise ValueError("minimum_observations must be at least 2")


def sanitize_returns(returns: pd.Series, maximum_absolute_return: float) -> pd.Series:
    """Return finite, economically valid observations with outliers winsorized."""
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan)
    clean = clean.dropna()
    clean = clean[clean > -1.0]
    return clean.clip(-maximum_absolute_return, maximum_absolute_return)


def _annualized_geometric_return(returns: pd.Series, periods_per_year: int) -> float:
    log_growth = np.log1p(returns)
    return float(np.expm1(log_growth.mean() * periods_per_year))


def _downside_deviation(returns: pd.Series, periods_per_year: int) -> float:
    downside = np.minimum(returns.to_numpy(dtype=float), 0.0)
    return float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(periods_per_year))


def performance_statistics(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    config: AnalyticsConfig | None = None,
) -> dict[str, float | int | None]:
    cfg = config or AnalyticsConfig()
    clean = sanitize_returns(returns, cfg.maximum_absolute_daily_return)
    if len(clean) < 2:
        return {
            "observations": len(clean),
            "annual_return": None,
            "annual_volatility": None,
        }

    annual_return = _annualized_geometric_return(clean, cfg.periods_per_year)
    annual_volatility = float(clean.std(ddof=1) * math.sqrt(cfg.periods_per_year))
    downside_deviation = _downside_deviation(clean, cfg.periods_per_year)
    arithmetic_annual_return = float(clean.mean() * cfg.periods_per_year)
    sharpe = None
    if annual_volatility > 0:
        sharpe = (arithmetic_annual_return - cfg.risk_free_rate) / annual_volatility
    sortino = None
    if downside_deviation > 0:
        sortino = (arithmetic_annual_return - cfg.risk_free_rate) / downside_deviation

    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    maximum_drawdown = float(drawdown.min())
    calmar = annual_return / abs(maximum_drawdown) if maximum_drawdown < 0 else None

    loss_quantile = float(clean.quantile(1.0 - cfg.confidence_level))
    tail_losses = clean[clean <= loss_quantile]
    historical_var = max(-loss_quantile, 0.0)
    historical_cvar = max(-float(tail_losses.mean()), 0.0)
    z_score = 1.6448536269514722
    parametric_var = max(
        -(float(clean.mean()) - z_score * float(clean.std(ddof=1))),
        0.0,
    )

    result: dict[str, float | int | None] = {
        "observations": len(clean),
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "downside_deviation": downside_deviation,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "maximum_drawdown": maximum_drawdown,
        "historical_var": historical_var,
        "historical_cvar": historical_cvar,
        "parametric_var": parametric_var,
        "best_day": float(clean.max()),
        "worst_day": float(clean.min()),
    }

    if benchmark is not None:
        benchmark_clean = sanitize_returns(
            benchmark,
            cfg.maximum_absolute_daily_return,
        )
        aligned = pd.concat(
            [clean.rename("portfolio"), benchmark_clean.rename("benchmark")],
            axis=1,
        ).dropna()
        benchmark_variance = float(aligned["benchmark"].var(ddof=1))
        if len(aligned) > 2 and benchmark_variance > 0:
            covariance = float(cast(Any, aligned.cov().at["portfolio", "benchmark"]))
            beta = covariance / benchmark_variance
            benchmark_annual = float(
                aligned["benchmark"].mean() * cfg.periods_per_year
            )
            alpha = arithmetic_annual_return - (
                cfg.risk_free_rate
                + beta * (benchmark_annual - cfg.risk_free_rate)
            )
            active = aligned["portfolio"] - aligned["benchmark"]
            tracking_error = float(
                active.std(ddof=1) * math.sqrt(cfg.periods_per_year)
            )
            information_ratio = None
            if tracking_error > 0:
                information_ratio = float(
                    active.mean() * cfg.periods_per_year / tracking_error
                )
            result.update(
                {
                    "beta": beta,
                    "alpha": alpha,
                    "tracking_error": tracking_error,
                    "information_ratio": information_ratio,
                }
            )
    return result


def diversification_statistics(
    weights: pd.Series,
    correlations: pd.DataFrame | None = None,
) -> dict[str, float | None]:
    clean = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    clean = clean[clean > 0]
    total = float(clean.sum())
    normalized = clean / total if total else clean
    hhi = float((normalized**2).sum()) if len(normalized) else 0.0
    entropy = float(-(normalized * np.log(normalized)).sum()) if len(normalized) else 0.0
    normalized_entropy = (
        entropy / math.log(len(normalized)) if len(normalized) > 1 else 0.0
    )
    average_correlation: float | None = None
    maximum_correlation: float | None = None
    if correlations is not None and len(correlations) > 1:
        matrix = correlations.to_numpy(dtype=float)
        upper = matrix[np.triu_indices_from(matrix, k=1)]
        finite = upper[np.isfinite(upper)]
        if len(finite):
            average_correlation = float(finite.mean())
            maximum_correlation = float(finite.max())
    return {
        "concentration_hhi": hhi,
        "effective_positions": 1.0 / hhi if hhi else 0.0,
        "entropy": entropy,
        "normalized_entropy": normalized_entropy,
        "average_pair_correlation": average_correlation,
        "maximum_pair_correlation": maximum_correlation,
    }


TRADING_DAYS = 252


@dataclass(frozen=True)
class PortfolioIntelligence:
    observation_count: int
    start_date: str | None
    end_date: str | None
    return_coverage: float
    expected_annual_return: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    maximum_drawdown: float | None
    calmar_ratio: float | None
    historical_var_95: float | None
    historical_cvar_95: float | None
    parametric_var_95: float | None
    downside_deviation: float | None
    worst_day: float | None
    best_day: float | None
    beta: float | None
    alpha: float | None
    tracking_error: float | None
    information_ratio: float | None
    average_correlation: float | None
    maximum_pair_correlation: float | None
    diversification_benefit: float | None
    concentration_hhi: float
    effective_positions: float
    entropy: float
    normalized_entropy: float
    largest_position_weight: float
    crypto_weight: float
    market_cap_exposure: Mapping[str, float]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioScorecard:
    overall_score: int
    grade: str
    status: str
    return_score: int
    risk_score: int
    diversification_score: int
    concentration_score: int
    data_quality_score: int
    notes: tuple[str, ...]


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    return numerator / denominator if denominator != 0.0 else None


def _maximum_drawdown(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def _market_cap_bucket(value: float | None) -> str:
    if value is None or not math.isfinite(value) or value <= 0.0:
        return "unknown"
    if value >= 200_000_000_000:
        return "mega_cap"
    if value >= 10_000_000_000:
        return "large_cap"
    if value >= 2_000_000_000:
        return "mid_cap"
    if value >= 300_000_000:
        return "small_cap"
    return "micro_cap"


def _compat_history_path(history_directory: Path, asset_id: str) -> Path:
    return history_directory / f"{asset_id.replace(':', '__')}.csv"


def _read_close_series(path: Path, asset_id: str) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=float, name=asset_id)
    frame = pd.read_csv(path)
    date_column = next(
        (name for name in ("timestamp", "date", "Date") if name in frame.columns),
        None,
    )
    close_column = next(
        (name for name in ("close", "Close", "adj_close", "Adj Close") if name in frame.columns),
        None,
    )
    if date_column is None or close_column is None or frame.empty:
        return pd.Series(dtype=float, name=asset_id)
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[close_column] = pd.to_numeric(frame[close_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, close_column]).drop_duplicates(date_column)
    prices = frame.set_index(date_column)[close_column].sort_index()
    return prices.pct_change(fill_method=None).dropna().rename(asset_id)


def load_return_matrix(
    targets: Sequence[TargetPosition],
    history_directory: Path,
) -> tuple[pd.DataFrame, float, tuple[str, ...]]:
    """Compatibility API used by the Phase 4.2 intelligence command and tests."""
    series: list[pd.Series] = []
    missing: list[str] = []
    target_ids = {target.asset_id for target in targets}
    for target in targets:
        values = _read_close_series(
            _compat_history_path(history_directory, target.asset_id),
            target.asset_id,
        )
        if values.empty:
            missing.append(target.asset_id)
        else:
            series.append(values)
    matrix = pd.concat(series, axis=1).sort_index() if series else pd.DataFrame()
    coverage = (len(target_ids) - len(missing)) / len(target_ids) if target_ids else 0.0
    return matrix, coverage, tuple(missing)


def _weighted_portfolio_returns(
    returns: pd.DataFrame,
    targets: Sequence[TargetPosition],
) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float, name="portfolio")
    weight_map = {target.asset_id: target.target_weight for target in targets}
    columns = [column for column in returns.columns if column in weight_map]
    if not columns:
        return pd.Series(dtype=float, name="portfolio")
    weights = pd.Series({column: weight_map[column] for column in columns}, dtype=float)
    weights /= float(weights.sum())
    available = returns[columns].notna().astype(float)
    row_weights = available.mul(weights, axis=1)
    denominators = row_weights.sum(axis=1).replace(0.0, np.nan)
    weighted = returns[columns].fillna(0.0).mul(weights, axis=1).sum(axis=1)
    return (weighted / denominators).dropna().rename("portfolio")


def _pair_correlation_stats(returns: pd.DataFrame) -> tuple[float | None, float | None]:
    if returns.shape[1] < 2:
        return None, None
    correlation = returns.corr(min_periods=20)
    mask = np.triu(np.ones(correlation.shape, dtype=bool), k=1)
    values = correlation.where(mask).stack().dropna()
    if values.empty:
        return None, None
    numeric_values = values.to_numpy(dtype=float)
    return float(np.mean(numeric_values)), float(np.max(numeric_values))


def _benchmark_metrics(
    portfolio: pd.Series,
    benchmark: pd.Series,
    risk_free_rate: float,
) -> tuple[float | None, float | None, float | None, float | None]:
    aligned = pd.concat([portfolio, benchmark.rename("benchmark")], axis=1).dropna()
    if len(aligned) < 2:
        return None, None, None, None
    benchmark_variance = float(aligned["benchmark"].var(ddof=1))
    covariance = float(aligned["portfolio"].cov(aligned["benchmark"]))
    beta = _safe_ratio(covariance, benchmark_variance)
    portfolio_return = _annualized_geometric_return(aligned["portfolio"], TRADING_DAYS)
    benchmark_return = _annualized_geometric_return(aligned["benchmark"], TRADING_DAYS)
    alpha = None
    if beta is not None:
        alpha = portfolio_return - (
            risk_free_rate + beta * (benchmark_return - risk_free_rate)
        )
    active = aligned["portfolio"] - aligned["benchmark"]
    tracking_error = float(active.std(ddof=1) * math.sqrt(TRADING_DAYS))
    information_ratio = _safe_ratio(
        float(active.mean() * TRADING_DAYS),
        tracking_error,
    )
    return beta, alpha, tracking_error, information_ratio


def analyze_portfolio(
    targets: Sequence[TargetPosition],
    return_matrix: pd.DataFrame,
    return_coverage: float,
    config: AnalyticsConfig | None = None,
    benchmark_returns: pd.Series | None = None,
    market_caps: Mapping[str, float | None] | None = None,
) -> PortfolioIntelligence:
    settings = config or AnalyticsConfig()
    portfolio = sanitize_returns(
        _weighted_portfolio_returns(return_matrix, targets),
        settings.maximum_absolute_daily_return,
    )
    diagnostics: list[str] = []
    if return_coverage < 1.0:
        diagnostics.append("Historical return coverage is incomplete.")
    if len(portfolio) < settings.minimum_observations:
        diagnostics.append(
            "Available history is below the configured minimum observation count."
        )

    expected_return = (
        _annualized_geometric_return(portfolio, settings.periods_per_year)
        if not portfolio.empty
        else None
    )
    volatility = (
        float(portfolio.std(ddof=1) * math.sqrt(settings.periods_per_year))
        if len(portfolio) >= 2
        else None
    )
    arithmetic_return = float(portfolio.mean() * settings.periods_per_year)
    sharpe = (
        _safe_ratio(arithmetic_return - settings.risk_free_rate, volatility)
        if volatility is not None
        else None
    )
    downside_deviation = (
        _downside_deviation(portfolio, settings.periods_per_year)
        if not portfolio.empty
        else None
    )
    sortino = (
        _safe_ratio(arithmetic_return - settings.risk_free_rate, downside_deviation)
        if downside_deviation is not None
        else None
    )
    maximum_drawdown = _maximum_drawdown(portfolio)
    calmar = (
        _safe_ratio(expected_return, abs(maximum_drawdown))
        if expected_return is not None and maximum_drawdown is not None
        else None
    )

    historical_var = historical_cvar = parametric_var = None
    if not portfolio.empty:
        quantile = float(portfolio.quantile(1.0 - settings.confidence_level))
        historical_var = max(-quantile, 0.0)
        tail = portfolio[portfolio <= quantile]
        historical_cvar = max(-float(tail.mean()), 0.0) if not tail.empty else historical_var
    if len(portfolio) >= 2:
        z_score = NormalDist().inv_cdf(settings.confidence_level)
        parametric_var = max(
            -(float(portfolio.mean()) - z_score * float(portfolio.std(ddof=1))),
            0.0,
        )

    beta = alpha = tracking_error = information_ratio = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        beta, alpha, tracking_error, information_ratio = _benchmark_metrics(
            portfolio,
            sanitize_returns(
                benchmark_returns,
                settings.maximum_absolute_daily_return,
            ),
            settings.risk_free_rate,
        )
    else:
        diagnostics.append(
            "Benchmark history is unavailable; relative metrics were omitted."
        )

    average_correlation, maximum_pair_correlation = _pair_correlation_stats(return_matrix)
    weights = {target.asset_id: target.target_weight for target in targets}
    standalone = sum(
        weights.get(str(column), 0.0)
        * float(return_matrix[column].std(ddof=1) * math.sqrt(TRADING_DAYS))
        for column in return_matrix.columns
    )
    diversification_benefit = (
        1.0 - volatility / standalone
        if volatility is not None and standalone > 0.0
        else None
    )
    position_weights = [target.target_weight for target in targets]
    concentration_hhi = sum(weight**2 for weight in position_weights)
    effective_positions = 1.0 / concentration_hhi if concentration_hhi > 0.0 else 0.0
    entropy = -sum(weight * math.log(weight) for weight in position_weights if weight > 0.0)
    normalized_entropy = (
        entropy / math.log(len(position_weights)) if len(position_weights) > 1 else 0.0
    )
    crypto_weight = sum(
        target.target_weight
        for target in targets
        if target.asset_class.lower() == "crypto"
    )
    market_cap_exposure: dict[str, float] = {}
    market_cap_map = market_caps or {}
    for target in targets:
        bucket = (
            "digital_assets"
            if target.asset_class.lower() == "crypto"
            else _market_cap_bucket(market_cap_map.get(target.asset_id))
        )
        market_cap_exposure[bucket] = (
            market_cap_exposure.get(bucket, 0.0) + target.target_weight
        )

    return PortfolioIntelligence(
        observation_count=len(portfolio),
        start_date=str(portfolio.index.min().date()) if not portfolio.empty else None,
        end_date=str(portfolio.index.max().date()) if not portfolio.empty else None,
        return_coverage=return_coverage,
        expected_annual_return=expected_return,
        annualized_volatility=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        maximum_drawdown=maximum_drawdown,
        calmar_ratio=calmar,
        historical_var_95=historical_var,
        historical_cvar_95=historical_cvar,
        parametric_var_95=parametric_var,
        downside_deviation=downside_deviation,
        worst_day=float(portfolio.min()) if not portfolio.empty else None,
        best_day=float(portfolio.max()) if not portfolio.empty else None,
        beta=beta,
        alpha=alpha,
        tracking_error=tracking_error,
        information_ratio=information_ratio,
        average_correlation=average_correlation,
        maximum_pair_correlation=maximum_pair_correlation,
        diversification_benefit=diversification_benefit,
        concentration_hhi=concentration_hhi,
        effective_positions=effective_positions,
        entropy=entropy,
        normalized_entropy=normalized_entropy,
        largest_position_weight=max(position_weights, default=0.0),
        crypto_weight=crypto_weight,
        market_cap_exposure=dict(sorted(market_cap_exposure.items())),
        diagnostics=tuple(diagnostics),
    )


def build_scorecard(intelligence: PortfolioIntelligence) -> PortfolioScorecard:
    data_quality = round(100.0 * intelligence.return_coverage)
    return_score = 50
    if intelligence.sharpe_ratio is not None:
        return_score = round(
            max(0.0, min(100.0, 50.0 + 25.0 * intelligence.sharpe_ratio))
        )
    risk_score = 50
    if intelligence.maximum_drawdown is not None:
        risk_score = round(
            max(0.0, min(100.0, 100.0 - 200.0 * abs(intelligence.maximum_drawdown)))
        )
    diversification_score = round(
        max(0.0, min(100.0, 100.0 * intelligence.normalized_entropy))
    )
    concentration_score = round(
        max(
            0.0,
            min(100.0, 100.0 * (1.0 - intelligence.largest_position_weight / 0.20)),
        )
    )
    overall = round(
        0.25 * return_score
        + 0.25 * risk_score
        + 0.20 * diversification_score
        + 0.15 * concentration_score
        + 0.15 * data_quality
    )
    if overall >= 90:
        grade = "A"
    elif overall >= 80:
        grade = "B"
    elif overall >= 70:
        grade = "C"
    elif overall >= 60:
        grade = "D"
    else:
        grade = "F"
    status = (
        "READY_FOR_PAPER_TRADING"
        if overall >= 75 and data_quality >= 80 and intelligence.observation_count >= 60
        else "REVIEW_REQUIRED"
    )
    notes = list(intelligence.diagnostics)
    if intelligence.crypto_weight > 0.15:
        notes.append("Crypto exposure exceeds 15%.")
    if intelligence.largest_position_weight > 0.10:
        notes.append("Largest position exceeds 10%.")
    return PortfolioScorecard(
        overall_score=overall,
        grade=grade,
        status=status,
        return_score=return_score,
        risk_score=risk_score,
        diversification_score=diversification_score,
        concentration_score=concentration_score,
        data_quality_score=data_quality,
        notes=tuple(notes),
    )


def write_intelligence_reports(
    intelligence: PortfolioIntelligence,
    scorecard: PortfolioScorecard,
    return_matrix: pd.DataFrame,
    output_directory: Path,
) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "portfolio_intelligence": output_directory / "portfolio_intelligence.json",
        "portfolio_scorecard": output_directory / "portfolio_scorecard.json",
        "correlation_matrix": output_directory / "correlation_matrix.csv",
        "covariance_matrix": output_directory / "covariance_matrix.csv",
        "portfolio_dashboard": output_directory / "portfolio_dashboard.html",
    }
    paths["portfolio_intelligence"].write_text(
        json.dumps(asdict(intelligence), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    paths["portfolio_scorecard"].write_text(
        json.dumps(asdict(scorecard), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return_matrix.corr(min_periods=20).to_csv(paths["correlation_matrix"])
    (return_matrix.cov(min_periods=20) * TRADING_DAYS).to_csv(
        paths["covariance_matrix"]
    )
    payload = json.dumps(
        {"intelligence": asdict(intelligence), "scorecard": asdict(scorecard)},
        sort_keys=True,
    )
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Atlas Portfolio Intelligence</title></head><body>"
        "<h1>Atlas Portfolio Intelligence</h1><pre id='app'></pre><script>"
        f"const data={payload};document.getElementById('app').textContent="
        "JSON.stringify(data,null,2);</script></body></html>"
    )
    paths["portfolio_dashboard"].write_text(html, encoding="utf-8")
    return {name: str(path) for name, path in paths.items()}


def read_market_caps(path: Path) -> dict[str, float | None]:
    if not path.exists():
        return {}
    values: dict[str, float | None] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            asset_id = row.get("asset_id", "").strip()
            raw = row.get("market_cap", "").strip()
            if not asset_id:
                continue
            try:
                values[asset_id] = float(raw) if raw else None
            except ValueError:
                values[asset_id] = None
    return values
