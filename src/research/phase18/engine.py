from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.research.phase13.engine import simulate_portfolio
from src.research.phase13.models import Phase13Config
from src.research.phase18.models import Phase18Config, Phase18Result

PHASE = "18.5"
VERSION = "0.18.5"


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
        "holding_period",
        "net_return_after_costs",
        "alpha_probability",
        "expected_value",
        "market_regime",
        "synthetic_volatility",
        "execution_score",
        "liquidity_score",
        "incremental_slippage_bps",
        "phase17_position_fraction",
        "execution_accepted",
        "model_recent_mean_return",
        "model_recent_win_rate",
        "rolling_symbol_correlation",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Phase 18 input is missing required columns: {missing}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result = result.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    numeric = [
        "holding_period",
        "net_return_after_costs",
        "alpha_probability",
        "expected_value",
        "synthetic_volatility",
        "execution_score",
        "liquidity_score",
        "incremental_slippage_bps",
        "phase17_position_fraction",
        "model_recent_mean_return",
        "model_recent_win_rate",
        "rolling_symbol_correlation",
    ]
    for column in numeric:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["execution_accepted"] = result["execution_accepted"].astype(bool)
    return result.dropna(subset=["timestamp", "symbol"]).reset_index(drop=True)


def _opportunity_components(row: pd.Series, config: Phase18Config) -> dict[str, float | str | bool]:
    probability = float(np.clip(_safe_float(row["alpha_probability"], 0.5), 0.0, 1.0))
    execution_score = float(np.clip(_safe_float(row["execution_score"]), 0.0, 1.0))
    liquidity = float(np.clip(_safe_float(row["liquidity_score"]), 0.0, 1.0))
    model_win_rate = float(np.clip(_safe_float(row["model_recent_win_rate"], 0.5), 0.0, 1.0))
    correlation = abs(_safe_float(row["rolling_symbol_correlation"]))
    phase17_fraction = float(np.clip(_safe_float(row["phase17_position_fraction"]), 0.0, 0.25))

    confidence_score = float(np.clip((probability - 0.50) / 0.25, 0.0, 1.0))
    model_health = float(np.clip(model_win_rate, 0.0, 1.0))
    diversification_score = float(np.clip(1.0 - correlation, 0.0, 1.0))
    soft_score = float(
        np.clip(
            config.soft_confidence_weight * confidence_score
            + config.soft_execution_weight * execution_score
            + config.soft_model_health_weight * model_health
            + config.soft_diversification_weight * diversification_score,
            0.0,
            1.0,
        )
    )
    score_probability = 0.50 + 0.25 * soft_score
    optimized_probability = float(
        np.clip(
            config.probability_anchor_weight * probability
            + (1.0 - config.probability_anchor_weight) * score_probability,
            0.50,
            0.75,
        )
    )
    volatility_multiplier = float(
        np.clip(
            1.0 - config.sizing_strength * (soft_score - 0.50),
            config.minimum_volatility_multiplier,
            config.maximum_volatility_multiplier,
        )
    )
    phase17_accepted = bool(row["execution_accepted"])
    accepted = bool(phase17_accepted and phase17_fraction > 0.0)
    return {
        "confidence_score_phase18": confidence_score,
        "model_health_score": model_health,
        "diversification_score": diversification_score,
        "soft_opportunity_score": soft_score,
        "optimized_probability": optimized_probability,
        "volatility_multiplier": volatility_multiplier,
        "capital_multiplier": 1.0 / volatility_multiplier,
        "phase18_position_fraction": phase17_fraction if accepted else 0.0,
        "phase18_accepted": accepted,
        "phase18_reason": "accepted_soft_weight" if accepted else "phase17_rejected",
        "liquidity_score_phase18": liquidity,
    }


def _prepare(frame: pd.DataFrame, config: Phase18Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        record: dict[str, Any] = {str(key): value for key, value in row.to_dict().items()}
        record.update(_opportunity_components(row, config))
        rows.append(record)
    scored = pd.DataFrame(rows)
    accepted = scored.loc[scored["phase18_accepted"]].copy()
    accepted["entry_timestamp"] = accepted["timestamp"]
    accepted["exit_timestamp"] = accepted["timestamp"] + pd.to_timedelta(
        accepted["holding_period"], unit="D"
    )
    accepted["probability"] = accepted["optimized_probability"]
    accepted["volatility"] = (
        accepted["synthetic_volatility"] * accepted["volatility_multiplier"]
    ).clip(0.005, 0.10)
    accepted["net_return"] = accepted["net_return_after_costs"] - (
        accepted["incremental_slippage_bps"] / 10_000.0
    )
    accepted["phase17_position_fraction"] = accepted["phase18_position_fraction"]
    return scored, accepted


def _metrics(
    executed: pd.DataFrame, equity: pd.DataFrame, initial_capital: float
) -> dict[str, float]:
    if equity.empty:
        return {
            "final_capital": initial_capital,
            "total_return": 0.0,
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
    maximum_drawdown = float(curve["drawdown"].max())
    gains = float(executed.loc[executed["pnl"] > 0, "pnl"].sum()) if not executed.empty else 0.0
    losses = (
        abs(float(executed.loc[executed["pnl"] < 0, "pnl"].sum())) if not executed.empty else 0.0
    )
    return {
        "final_capital": final_capital,
        "total_return": final_capital / initial_capital - 1.0,
        "cagr": cagr,
        "sharpe": float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.0,
        "sortino": float(returns.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0,
        "calmar": cagr / maximum_drawdown if maximum_drawdown > 0 else 0.0,
        "maximum_drawdown": maximum_drawdown,
        "profit_factor": gains / losses if losses > 0 else 0.0,
        "average_gross_exposure": float(curve["gross_exposure"].mean()),
    }


def _bootstrap_difference(
    phase18: pd.DataFrame, phase17: pd.DataFrame, samples: int, seed: int
) -> pd.DataFrame:
    new = phase18["net_return"].to_numpy(dtype=float) if not phase18.empty else np.array([])
    old_col = "net_return" if "net_return" in phase17.columns else "net_return_after_costs"
    old = phase17[old_col].to_numpy(dtype=float) if not phase17.empty else np.array([])
    if len(new) == 0 or len(old) == 0:
        return pd.DataFrame(
            [
                {
                    "mean_difference": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.0,
                    "probability_improvement": 0.0,
                }
            ]
        )
    rng = np.random.default_rng(seed)
    differences = np.array(
        [
            rng.choice(new, size=len(new), replace=True).mean()
            - rng.choice(old, size=len(old), replace=True).mean()
            for _ in range(samples)
        ]
    )
    return pd.DataFrame(
        [
            {
                "mean_difference": float(new.mean() - old.mean()),
                "ci_low": float(np.quantile(differences, 0.025)),
                "ci_high": float(np.quantile(differences, 0.975)),
                "probability_improvement": float((differences > 0.0).mean()),
            }
        ]
    )


def run_phase18(config: Phase18Config) -> Phase18Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    source = _normalize(pd.read_csv(config.phase17_scores_path))
    scored, candidates = _prepare(source, config)
    portfolio_config = Phase13Config(
        initial_capital=config.initial_capital,
        target_risk_per_trade=0.005,
        maximum_position_fraction=config.maximum_position_fraction,
        maximum_gross_exposure=config.maximum_gross_exposure,
        maximum_asset_class_exposure=config.maximum_asset_class_exposure,
        maximum_open_positions=config.maximum_open_positions,
        portfolio_drawdown_limit=config.portfolio_drawdown_limit,
        maximum_allowed_drawdown=0.30,
    )
    executed, rejected, equity, reconciliation = simulate_portfolio(candidates, portfolio_config)
    phase18_metrics = _metrics(executed, equity, config.initial_capital)
    phase17_equity = pd.read_csv(config.phase17_equity_path)
    phase17_executed = pd.read_csv(config.phase17_executed_path)
    phase17_metrics = _metrics(phase17_executed, phase17_equity, config.initial_capital)
    comparison = pd.DataFrame(
        [
            {"portfolio": "phase17_4", **phase17_metrics},
            {"portfolio": "phase18_5", **phase18_metrics},
        ]
    )
    fold_column = "phase15_fold" if "phase15_fold" in source else "fold"
    fold_rows: list[dict[str, float | int]] = []
    for fold, fold_source in source.groupby(fold_column, sort=True):
        _, fold_candidates = _prepare(fold_source, config)
        fold_executed, _, fold_equity, _ = simulate_portfolio(fold_candidates, portfolio_config)
        fold_rows.append(
            {"fold": int(str(fold)), **_metrics(fold_executed, fold_equity, config.initial_capital)}
        )
    folds = pd.DataFrame(fold_rows)
    positive_fold_rate = float((folds["total_return"] > 0.0).mean()) if not folds.empty else 0.0
    bootstrap = _bootstrap_difference(
        executed, phase17_executed, config.bootstrap_samples, config.random_seed
    )
    diagnostics = bool(
        not equity.empty
        and abs(float(reconciliation["equity_reconciliation_difference"])) <= 1e-8
        and np.isfinite(list(phase18_metrics.values())).all()
    )
    sharpe_improvement = phase18_metrics["sharpe"] - phase17_metrics["sharpe"]
    pf_improvement = phase18_metrics["profit_factor"] - phase17_metrics["profit_factor"]
    dd_deterioration = phase18_metrics["maximum_drawdown"] - phase17_metrics["maximum_drawdown"]
    bootstrap_probability = float(bootstrap.iloc[0]["probability_improvement"])
    approved = bool(
        diagnostics
        and sharpe_improvement >= config.minimum_sharpe_improvement
        and pf_improvement >= config.minimum_profit_factor_improvement
        and dd_deterioration <= config.maximum_drawdown_deterioration
        and positive_fold_rate >= config.minimum_positive_fold_rate
        and bootstrap_probability >= config.minimum_bootstrap_probability
        and phase18_metrics["average_gross_exposure"]
        >= config.minimum_capital_utilization_ratio * phase17_metrics["average_gross_exposure"]
    )
    artifacts = {
        "opportunity_ranking": str(config.output_root / "opportunity_ranking.csv"),
        "capital_allocation_history": str(config.output_root / "capital_allocation_history.csv"),
        "portfolio_risk_breakdown": str(config.output_root / "portfolio_risk_breakdown.csv"),
        "opportunity_cost": str(config.output_root / "opportunity_cost.csv"),
        "model_allocation": str(config.output_root / "model_allocation.csv"),
        "phase17_vs_phase18": str(config.output_root / "phase17_vs_phase18.csv"),
        "fold_comparison": str(config.output_root / "fold_comparison.csv"),
        "bootstrap_validation": str(config.output_root / "bootstrap_validation.csv"),
        "executed_trades": str(config.output_root / "phase18_executed_trades.csv"),
        "rejected_signals": str(config.output_root / "phase18_rejected_signals.csv"),
        "equity_curve": str(config.output_root / "phase18_equity_curve.csv"),
        "dashboard": str(config.output_root / "phase18_dashboard.json"),
        "signoff": str(config.output_root / "phase18_final_signoff.json"),
    }
    scored.to_csv(artifacts["opportunity_ranking"], index=False)
    scored[
        [
            "timestamp",
            "symbol",
            "asset_class",
            "phase17_position_fraction",
            "capital_multiplier",
            "phase18_position_fraction",
            "soft_opportunity_score",
            "optimized_probability",
            "volatility_multiplier",
            "phase18_accepted",
        ]
    ].to_csv(artifacts["capital_allocation_history"], index=False)
    scored.groupby("asset_class", as_index=False).agg(
        candidates=("symbol", "size"),
        acceptance_rate=("phase18_accepted", "mean"),
        mean_position=("phase18_position_fraction", "mean"),
        mean_correlation=("rolling_symbol_correlation", "mean"),
    ).to_csv(artifacts["portfolio_risk_breakdown"], index=False)
    scored.loc[
        ~scored["phase18_accepted"],
        [
            "timestamp",
            "symbol",
            "phase18_reason",
            "soft_opportunity_score",
            "expected_value",
            "net_return_after_costs",
        ],
    ].to_csv(artifacts["opportunity_cost"], index=False)
    model_column = "champion_model" if "champion_model" in scored else "asset_class"
    scored.groupby(model_column, as_index=False).agg(
        candidates=("symbol", "size"),
        acceptance_rate=("phase18_accepted", "mean"),
        mean_health=("model_health_score", "mean"),
        mean_multiplier=("capital_multiplier", "mean"),
    ).to_csv(artifacts["model_allocation"], index=False)
    comparison.to_csv(artifacts["phase17_vs_phase18"], index=False)
    folds.to_csv(artifacts["fold_comparison"], index=False)
    bootstrap.to_csv(artifacts["bootstrap_validation"], index=False)
    executed.to_csv(artifacts["executed_trades"], index=False)
    rejected.to_csv(artifacts["rejected_signals"], index=False)
    equity.to_csv(artifacts["equity_curve"], index=False)
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "source_candidates": len(source),
        "optimized_candidates": len(candidates),
        "executed_trades": len(executed),
        "rejected_trades": len(rejected),
        "phase17_metrics": phase17_metrics,
        "phase18_metrics": phase18_metrics,
        "capital_utilization_ratio": phase18_metrics["average_gross_exposure"]
        / max(phase17_metrics["average_gross_exposure"], 1e-12),
        "sharpe_improvement": sharpe_improvement,
        "profit_factor_improvement": pf_improvement,
        "drawdown_deterioration": dd_deterioration,
        "positive_fold_rate": positive_fold_rate,
        "bootstrap_probability_improvement": bootstrap_probability,
        "diagnostics_passed": diagnostics,
        "approved_for_phase19_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    signoff = {
        "phase": PHASE,
        "version": VERSION,
        "status": "PHASE18_5_SOFT_PORTFOLIO_OPTIMIZATION_COMPLETE",
        "diagnostics_passed": diagnostics,
        "approved_for_phase19_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "promotion_checks": {
            "sharpe_improvement": sharpe_improvement >= config.minimum_sharpe_improvement,
            "profit_factor_improvement": pf_improvement >= config.minimum_profit_factor_improvement,
            "drawdown_control": dd_deterioration <= config.maximum_drawdown_deterioration,
            "fold_stability": positive_fold_rate >= config.minimum_positive_fold_rate,
            "bootstrap_probability": bootstrap_probability >= config.minimum_bootstrap_probability,
            "capital_utilization": phase18_metrics["average_gross_exposure"]
            >= config.minimum_capital_utilization_ratio * phase17_metrics["average_gross_exposure"],
        },
        "notes": [
            "Soft optimization uses only fields available before each candidate trade.",
            "Phase 17 accepted opportunities are preserved; scores alter priority and sizing continuously.",
            "Phase 17 execution costs remain in force.",
            "No broker orders are submitted.",
        ],
    }
    Path(artifacts["dashboard"]).write_text(json.dumps(dashboard, indent=2, default=str))
    Path(artifacts["signoff"]).write_text(json.dumps(signoff, indent=2, default=str))
    return Phase18Result(
        len(source),
        len(candidates),
        len(executed),
        len(rejected),
        diagnostics,
        approved,
        False,
        False,
        str(config.output_root),
        artifacts,
    )
