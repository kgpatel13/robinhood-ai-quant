from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.research.phase13.engine import confidence_multiplier, simulate_portfolio
from src.research.phase13.models import Phase13Config
from src.research.phase16.models import Phase16Config, Phase16Result

PHASE = "16.4"
VERSION = "0.16.4"

REGIME_MULTIPLIERS: dict[str, float] = {
    "bull_low_volatility": 1.10,
    "bull_high_volatility": 0.85,
    "sideways": 0.75,
    "bear_low_volatility": 0.65,
    "bear_high_volatility": 0.45,
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(cast(Any, value))
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "timestamp",
        "symbol",
        "asset_class",
        "net_return_after_costs",
        "alpha_probability",
        "predicted_net_return",
        "expected_value",
        "market_regime",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Phase 16 input is missing required columns: {missing}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result = result.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    numeric = [
        "net_return_after_costs",
        "alpha_probability",
        "predicted_net_return",
        "expected_value",
        "benchmark_volatility_20d",
    ]
    for column in numeric:
        if column not in result:
            result[column] = np.nan
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["benchmark_volatility_20d"] = result["benchmark_volatility_20d"].fillna(0.02)
    if "holding_period" not in result:
        result["holding_period"] = 1
    result["holding_period"] = pd.to_numeric(result["holding_period"], errors="coerce").fillna(1)
    return result.dropna(
        subset=["timestamp", "net_return_after_costs", "alpha_probability"]
    ).reset_index(drop=True)


def _add_leakage_safe_intelligence(frame: pd.DataFrame, config: Phase16Config) -> pd.DataFrame:
    result = frame.copy()
    market_return = result.groupby("timestamp", sort=True)["net_return_after_costs"].mean()
    result["market_realized_return"] = result["timestamp"].map(market_return)
    result["rolling_symbol_correlation"] = np.nan
    result["model_recent_mean_return"] = np.nan
    result["model_recent_win_rate"] = np.nan
    result["model_active"] = True

    for _, index in result.groupby("symbol", sort=False).groups.items():
        ordered = result.loc[index].sort_values("timestamp")
        correlation = (
            ordered["net_return_after_costs"]
            .rolling(40, min_periods=10)
            .corr(ordered["market_realized_return"])
            .shift(1)
        )
        result.loc[ordered.index, "rolling_symbol_correlation"] = correlation.to_numpy()

    model_column = "base_champion_model" if "base_champion_model" in result else "champion_model"
    if model_column not in result:
        result[model_column] = "unknown"
    for _, index in result.groupby(model_column, sort=False).groups.items():
        ordered = result.loc[index].sort_values("timestamp")
        returns = ordered["net_return_after_costs"]
        prior_mean = returns.rolling(config.model_lookback_trades, min_periods=1).mean().shift(1)
        prior_win = (
            returns.gt(0)
            .astype(float)
            .rolling(config.model_lookback_trades, min_periods=1)
            .mean()
            .shift(1)
        )
        prior_count = pd.Series(np.arange(len(ordered)), index=ordered.index)
        active = (prior_count < config.minimum_model_observations) | (prior_mean > 0.0)
        result.loc[ordered.index, "model_recent_mean_return"] = prior_mean.to_numpy()
        result.loc[ordered.index, "model_recent_win_rate"] = prior_win.to_numpy()
        result.loc[ordered.index, "model_active"] = active.to_numpy()

    result["rolling_symbol_correlation"] = result["rolling_symbol_correlation"].fillna(0.0)
    result["model_recent_mean_return"] = result["model_recent_mean_return"].fillna(0.0)
    result["model_recent_win_rate"] = result["model_recent_win_rate"].fillna(0.5)
    return result


def _adaptive_fraction(row: pd.Series, config: Phase16Config) -> tuple[float, dict[str, float]]:
    probability = float(np.clip(_safe_float(row["alpha_probability"], 0.5), 0.0, 1.0))
    volatility = float(
        np.clip(abs(_safe_float(row["benchmark_volatility_20d"], 0.02)), 0.005, 0.08)
    )
    expected_return = max(_safe_float(row["predicted_net_return"]), 0.0)
    expected_value = max(_safe_float(row["expected_value"]), 0.0)
    confidence_score = float(np.clip((probability - 0.50) / 0.25, 0.0, 1.0))
    ev_score = float(np.clip(expected_value / 0.05, 0.0, 1.5))
    volatility_target = config.target_risk_per_trade / volatility
    payoff = max(expected_return, 0.001)
    loss_estimate = max(
        volatility * np.sqrt(max(_safe_float(row["holding_period"], 1.0), 1.0)), 0.005
    )
    odds = payoff / loss_estimate
    raw_kelly = max((probability * (odds + 1.0) - 1.0) / max(odds, 1e-9), 0.0)
    kelly_fraction = min(raw_kelly * config.fractional_kelly, config.maximum_kelly_fraction)
    regime_multiplier = REGIME_MULTIPLIERS.get(str(row["market_regime"]), 0.70)
    correlation = abs(_safe_float(row["rolling_symbol_correlation"]))
    if correlation >= config.correlation_hard_limit:
        correlation_multiplier = 0.25
    elif correlation > config.correlation_soft_limit:
        span = config.correlation_hard_limit - config.correlation_soft_limit
        correlation_multiplier = 1.0 - 0.75 * ((correlation - config.correlation_soft_limit) / span)
    else:
        correlation_multiplier = 1.0
    model_multiplier = 1.0 if bool(row["model_active"]) else 0.0
    conviction = 0.35 + 0.40 * confidence_score + 0.25 * min(ev_score, 1.0)
    fraction = min(volatility_target * conviction, kelly_fraction or volatility_target)
    fraction *= regime_multiplier * correlation_multiplier * model_multiplier
    fraction = float(np.clip(fraction, 0.0, config.maximum_position_fraction))
    if 0.0 < fraction < config.minimum_position_fraction:
        fraction = 0.0
    components = {
        "confidence_score": confidence_score,
        "ev_score": ev_score,
        "raw_kelly": raw_kelly,
        "kelly_fraction": kelly_fraction,
        "regime_multiplier": regime_multiplier,
        "correlation_multiplier": correlation_multiplier,
        "model_multiplier": model_multiplier,
        "adaptive_position_fraction": fraction,
    }
    return fraction, components


def _prepare_adaptive_trades(
    frame: pd.DataFrame, config: Phase16Config
) -> tuple[pd.DataFrame, pd.DataFrame]:
    intelligent = _add_leakage_safe_intelligence(frame, config)
    rows: list[dict[str, Any]] = []
    for _, row in intelligent.iterrows():
        fraction, components = _adaptive_fraction(row, config)
        record: dict[str, Any] = {str(key): value for key, value in row.to_dict().items()}
        record.update(components)
        rows.append(record)
    allocations = pd.DataFrame(rows)
    confidence_config = Phase13Config(
        target_risk_per_trade=config.target_risk_per_trade,
        maximum_position_fraction=config.maximum_position_fraction,
    )
    multiplier = allocations["alpha_probability"].map(
        lambda value: confidence_multiplier(float(value), confidence_config)
    )
    desired = allocations["adaptive_position_fraction"].replace(0.0, np.nan)
    synthetic_volatility = config.target_risk_per_trade * multiplier / desired
    allocations["synthetic_volatility"] = synthetic_volatility.clip(0.005, 0.08).fillna(0.08)
    accepted = allocations.loc[allocations["adaptive_position_fraction"] > 0.0].copy()
    accepted["entry_timestamp"] = accepted["timestamp"]
    accepted["exit_timestamp"] = accepted["timestamp"] + pd.to_timedelta(
        accepted["holding_period"], unit="D"
    )
    accepted["probability"] = accepted["alpha_probability"]
    accepted["volatility"] = accepted["synthetic_volatility"]
    accepted["net_return"] = accepted["net_return_after_costs"]
    return allocations, accepted


def _metrics(
    executed: pd.DataFrame, equity: pd.DataFrame, initial_capital: float
) -> dict[str, float]:
    if equity.empty:
        return {
            "final_capital": initial_capital,
            "cagr": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "maximum_drawdown": 0.0,
            "profit_factor": 0.0,
            "average_gross_exposure": 0.0,
        }
    curve = equity.copy()
    curve["timestamp"] = pd.to_datetime(curve["timestamp"], utc=True)
    daily = curve.sort_values("timestamp").groupby(curve["timestamp"].dt.date).tail(1)
    returns = daily["capital"].pct_change().dropna()
    years = max((curve["timestamp"].max() - curve["timestamp"].min()).days / 365.25, 1 / 365.25)
    final_capital = float(curve.iloc[-1]["capital"])
    cagr = (final_capital / initial_capital) ** (1.0 / years) - 1.0
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    downside = returns[returns < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sharpe = float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    sortino = float(returns.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0
    maximum_drawdown = float(curve["drawdown"].max())
    gains = float(executed.loc[executed["pnl"] > 0, "pnl"].sum()) if not executed.empty else 0.0
    losses = (
        abs(float(executed.loc[executed["pnl"] < 0, "pnl"].sum())) if not executed.empty else 0.0
    )
    return {
        "final_capital": final_capital,
        "total_return": final_capital / initial_capital - 1.0,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": cagr / maximum_drawdown if maximum_drawdown > 0 else 0.0,
        "maximum_drawdown": maximum_drawdown,
        "profit_factor": gains / losses if losses > 0 else 0.0,
        "average_gross_exposure": float(curve["gross_exposure"].mean()),
    }


def _bootstrap(executed: pd.DataFrame, samples: int, seed: int) -> pd.DataFrame:
    returns = executed["net_return"].to_numpy(dtype=float) if not executed.empty else np.array([])
    if len(returns) == 0:
        return pd.DataFrame([{"mean_return": 0.0, "ci_low": 0.0, "ci_high": 0.0}])
    rng = np.random.default_rng(seed)
    means = np.array(
        [rng.choice(returns, size=len(returns), replace=True).mean() for _ in range(samples)]
    )
    return pd.DataFrame(
        [
            {
                "mean_return": float(returns.mean()),
                "ci_low": float(np.quantile(means, 0.025)),
                "ci_high": float(np.quantile(means, 0.975)),
                "probability_positive": float((means > 0.0).mean()),
            }
        ]
    )


def _load_phase15_metrics(config: Phase16Config) -> dict[str, float]:
    equity = pd.read_csv(config.phase15_equity_path)
    executed = pd.read_csv(config.phase15_executed_path)
    return _metrics(executed, equity, config.initial_capital)


def run_phase16(config: Phase16Config) -> Phase16Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    source = _normalize(pd.read_csv(config.selected_trades_path))
    allocations, adaptive = _prepare_adaptive_trades(source, config)
    phase13_config = Phase13Config(
        initial_capital=config.initial_capital,
        target_risk_per_trade=config.target_risk_per_trade,
        maximum_position_fraction=config.maximum_position_fraction,
        maximum_gross_exposure=config.maximum_gross_exposure,
        maximum_asset_class_exposure=config.maximum_asset_class_exposure,
        maximum_open_positions=config.maximum_open_positions,
        portfolio_drawdown_limit=config.drawdown_hard_limit,
        maximum_allowed_drawdown=0.30,
    )
    executed, rejected, equity, base_metrics = simulate_portfolio(adaptive, phase13_config)
    adaptive_metrics = _metrics(executed, equity, config.initial_capital)
    phase15_metrics = _load_phase15_metrics(config)
    comparison = pd.DataFrame(
        [
            {"portfolio": "phase15_6", **phase15_metrics},
            {"portfolio": "phase16_4", **adaptive_metrics},
        ]
    )
    fold_rows: list[dict[str, float | int]] = []
    for fold, fold_source in source.groupby("phase15_fold", sort=True):
        fold_allocations, fold_adaptive = _prepare_adaptive_trades(fold_source, config)
        del fold_allocations
        fold_executed, _, fold_equity, _ = simulate_portfolio(fold_adaptive, phase13_config)
        fold_metric = _metrics(fold_executed, fold_equity, config.initial_capital)
        fold_rows.append({"fold": int(str(fold)), **fold_metric})
    fold_comparison = pd.DataFrame(fold_rows)
    positive_fold_rate = (
        float((fold_comparison["total_return"] > 0.0).mean()) if not fold_comparison.empty else 0.0
    )
    bootstrap = _bootstrap(executed, config.bootstrap_samples, config.random_seed)
    rank_correlation = spearmanr(
        allocations["expected_value"], allocations["net_return_after_costs"], nan_policy="omit"
    )
    correlation_value = _safe_float(rank_correlation.statistic)
    diagnostics = bool(
        not equity.empty
        and abs(float(base_metrics["equity_reconciliation_difference"])) <= 1e-8
        and np.isfinite(list(adaptive_metrics.values())).all()
    )
    sharpe_improvement = adaptive_metrics["sharpe"] - phase15_metrics["sharpe"]
    profit_factor_improvement = adaptive_metrics["profit_factor"] - phase15_metrics["profit_factor"]
    drawdown_deterioration = (
        adaptive_metrics["maximum_drawdown"] - phase15_metrics["maximum_drawdown"]
    )
    approved = bool(
        diagnostics
        and sharpe_improvement >= config.minimum_sharpe_improvement
        and profit_factor_improvement >= config.minimum_profit_factor_improvement
        and drawdown_deterioration <= config.maximum_drawdown_deterioration
        and positive_fold_rate >= config.minimum_positive_fold_rate
        and float(bootstrap.iloc[0]["ci_low"]) > 0.0
    )
    artifacts = {
        "adaptive_allocations": str(config.output_root / "adaptive_allocations.csv"),
        "risk_budget_history": str(config.output_root / "risk_budget_history.csv"),
        "model_weight_history": str(config.output_root / "model_weight_history.csv"),
        "regime_allocation": str(config.output_root / "regime_allocation.csv"),
        "correlation_exposure": str(config.output_root / "correlation_exposure.csv"),
        "stress_test_results": str(config.output_root / "stress_test_results.csv"),
        "phase15_vs_phase16": str(config.output_root / "phase15_vs_phase16.csv"),
        "fold_comparison": str(config.output_root / "fold_comparison.csv"),
        "bootstrap_validation": str(config.output_root / "bootstrap_validation.csv"),
        "executed_trades": str(config.output_root / "phase16_executed_trades.csv"),
        "rejected_signals": str(config.output_root / "phase16_rejected_signals.csv"),
        "equity_curve": str(config.output_root / "phase16_equity_curve.csv"),
        "dashboard": str(config.output_root / "phase16_dashboard.json"),
        "signoff": str(config.output_root / "phase16_final_signoff.json"),
    }
    allocations.to_csv(artifacts["adaptive_allocations"], index=False)
    allocations[
        ["timestamp", "symbol", "market_regime", "regime_multiplier", "adaptive_position_fraction"]
    ].to_csv(artifacts["risk_budget_history"], index=False)
    model_column = (
        "base_champion_model" if "base_champion_model" in allocations else "champion_model"
    )
    allocations[
        [
            "timestamp",
            model_column,
            "model_recent_mean_return",
            "model_recent_win_rate",
            "model_active",
        ]
    ].to_csv(artifacts["model_weight_history"], index=False)
    allocations.groupby("market_regime", as_index=False).agg(
        trades=("symbol", "size"),
        mean_position_fraction=("adaptive_position_fraction", "mean"),
        mean_expected_value=("expected_value", "mean"),
    ).to_csv(artifacts["regime_allocation"], index=False)
    allocations[
        [
            "timestamp",
            "symbol",
            "rolling_symbol_correlation",
            "correlation_multiplier",
            "adaptive_position_fraction",
        ]
    ].to_csv(artifacts["correlation_exposure"], index=False)
    stress = pd.DataFrame(
        [
            {"scenario": "base", **adaptive_metrics},
            {
                "scenario": "returns_minus_10pct",
                "estimated_final_capital": config.initial_capital
                + float(executed["pnl"].sum()) * 0.90,
            },
            {
                "scenario": "returns_minus_25pct",
                "estimated_final_capital": config.initial_capital
                + float(executed["pnl"].sum()) * 0.75,
            },
            {
                "scenario": "double_cost_proxy",
                "estimated_final_capital": config.initial_capital
                + float(executed["pnl"].sum())
                - float(executed["allocated_capital"].sum()) * 0.001,
            },
        ]
    )
    stress.to_csv(artifacts["stress_test_results"], index=False)
    comparison.to_csv(artifacts["phase15_vs_phase16"], index=False)
    fold_comparison.to_csv(artifacts["fold_comparison"], index=False)
    bootstrap.to_csv(artifacts["bootstrap_validation"], index=False)
    executed.to_csv(artifacts["executed_trades"], index=False)
    rejected.to_csv(artifacts["rejected_signals"], index=False)
    equity.to_csv(artifacts["equity_curve"], index=False)
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "source_trades": len(source),
        "adaptive_candidates": len(adaptive),
        "executed_trades": len(executed),
        "rejected_trades": len(rejected),
        "phase15_metrics": phase15_metrics,
        "phase16_metrics": adaptive_metrics,
        "sharpe_improvement": sharpe_improvement,
        "profit_factor_improvement": profit_factor_improvement,
        "drawdown_deterioration": drawdown_deterioration,
        "positive_fold_rate": positive_fold_rate,
        "expected_value_rank_correlation": correlation_value,
        "diagnostics_passed": diagnostics,
        "approved_for_phase17_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    signoff = {
        "phase": PHASE,
        "version": VERSION,
        "status": "PHASE16_ADAPTIVE_PORTFOLIO_INTELLIGENCE_COMPLETE",
        "diagnostics_passed": diagnostics,
        "approved_for_phase17_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "promotion_checks": {
            "sharpe_improvement": sharpe_improvement >= config.minimum_sharpe_improvement,
            "profit_factor_improvement": profit_factor_improvement
            >= config.minimum_profit_factor_improvement,
            "drawdown_control": drawdown_deterioration <= config.maximum_drawdown_deterioration,
            "fold_stability": positive_fold_rate >= config.minimum_positive_fold_rate,
            "bootstrap_positive_ci": float(bootstrap.iloc[0]["ci_low"]) > 0.0,
        },
        "notes": [
            "Sizing uses only information available before each trade.",
            "Phase 13 execution constraints remain authoritative.",
            "No broker orders are submitted.",
        ],
    }
    Path(artifacts["dashboard"]).write_text(json.dumps(dashboard, indent=2, default=str))
    Path(artifacts["signoff"]).write_text(json.dumps(signoff, indent=2, default=str))
    return Phase16Result(
        source_trades=len(source),
        executed_trades=len(executed),
        rejected_trades=len(rejected),
        diagnostics_passed=diagnostics,
        approved_for_phase17_review=approved,
        approved_for_paper_trading=False,
        approved_for_live_trading=False,
        output=str(config.output_root),
        artifacts=artifacts,
    )
