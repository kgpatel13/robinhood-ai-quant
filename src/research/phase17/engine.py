from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.research.phase13.engine import simulate_portfolio
from src.research.phase13.models import Phase13Config
from src.research.phase17.models import Phase17Config, Phase17Result

PHASE = "17.4"
VERSION = "0.17.4"


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
        "adaptive_position_fraction",
        "synthetic_volatility",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Phase 17 input is missing required columns: {missing}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result = result.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    numeric = [
        "holding_period",
        "net_return_after_costs",
        "alpha_probability",
        "expected_value",
        "adaptive_position_fraction",
        "synthetic_volatility",
        "benchmark_volatility_20d",
        "rolling_symbol_correlation",
        "symbol_history_count",
        "model_recent_mean_return",
    ]
    for column in numeric:
        if column not in result:
            result[column] = 0.0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result.dropna(subset=["timestamp", "symbol"]).reset_index(drop=True)


def _execution_components(row: pd.Series, config: Phase17Config) -> dict[str, float | str | bool]:
    volatility = float(
        np.clip(abs(_safe_float(row["benchmark_volatility_20d"], 0.02)), 0.005, 0.10)
    )
    position = float(np.clip(_safe_float(row["adaptive_position_fraction"]), 0.0, 0.25))
    history = max(_safe_float(row["symbol_history_count"]), 0.0)
    correlation = abs(_safe_float(row["rolling_symbol_correlation"]))
    probability = float(np.clip(_safe_float(row["alpha_probability"], 0.5), 0.0, 1.0))
    expected_value = max(_safe_float(row["expected_value"]), 0.0)
    asset_class = str(row["asset_class"]).lower()

    history_score = float(np.clip(np.log1p(history) / np.log(501.0), 0.0, 1.0))
    volatility_score = float(np.clip(1.0 - (volatility - 0.005) / 0.095, 0.0, 1.0))
    liquidity_floor = (
        config.crypto_liquidity_floor if asset_class == "crypto" else config.stock_liquidity_floor
    )
    liquidity_score = float(
        np.clip(liquidity_floor + 0.25 * history_score + 0.20 * volatility_score, 0.0, 1.0)
    )
    market_impact_bps = 6.0 + 22.0 * position + 18.0 * volatility + 8.0 * correlation
    incremental_slippage_bps = float(
        np.clip(
            market_impact_bps * (1.15 - liquidity_score),
            0.0,
            config.maximum_incremental_slippage_bps,
        )
    )
    confidence_score = float(np.clip((probability - 0.50) / 0.25, 0.0, 1.0))
    ev_score = float(np.clip(expected_value / 0.05, 0.0, 1.0))
    regime_score = {
        "bull_low_volatility": 1.0,
        "bull_high_volatility": 0.78,
        "sideways": 0.70,
        "bear_low_volatility": 0.62,
        "bear_high_volatility": 0.45,
    }.get(str(row["market_regime"]), 0.60)
    execution_score = float(
        np.clip(
            0.35 * liquidity_score
            + 0.30 * confidence_score
            + 0.20 * ev_score
            + 0.15 * regime_score,
            0.0,
            1.0,
        )
    )
    capital_efficiency_multiplier = float(np.clip(0.65 + 0.45 * execution_score, 0.55, 1.10))
    adjusted_fraction = float(
        np.clip(position * capital_efficiency_multiplier, 0.0, config.maximum_position_fraction)
    )
    accepted = bool(position > 0.0 and execution_score >= config.minimum_execution_score)
    reason = (
        "accepted"
        if accepted
        else ("zero_phase16_allocation" if position <= 0 else "execution_score")
    )
    return {
        "liquidity_score": liquidity_score,
        "incremental_slippage_bps": incremental_slippage_bps,
        "execution_score": execution_score,
        "capital_efficiency_multiplier": capital_efficiency_multiplier,
        "phase17_position_fraction": adjusted_fraction if accepted else 0.0,
        "execution_accepted": accepted,
        "execution_reason": reason,
    }


def _prepare(frame: pd.DataFrame, config: Phase17Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        record: dict[str, Any] = {str(key): value for key, value in row.to_dict().items()}
        record.update(_execution_components(row, config))
        rows.append(record)
    scored = pd.DataFrame(rows)
    accepted = scored.loc[scored["execution_accepted"]].copy()
    accepted["entry_timestamp"] = accepted["timestamp"]
    accepted["exit_timestamp"] = accepted["timestamp"] + pd.to_timedelta(
        accepted["holding_period"], unit="D"
    )
    accepted["probability"] = accepted["alpha_probability"]
    accepted["volatility"] = accepted["synthetic_volatility"].clip(0.005, 0.10)
    accepted["net_return"] = accepted["net_return_after_costs"] - (
        accepted["incremental_slippage_bps"] / 10_000.0
    )
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


def _bootstrap(executed: pd.DataFrame, samples: int, seed: int) -> pd.DataFrame:
    returns = executed["net_return"].to_numpy(dtype=float) if not executed.empty else np.array([])
    if len(returns) == 0:
        return pd.DataFrame(
            [{"mean_return": 0.0, "ci_low": 0.0, "ci_high": 0.0, "probability_positive": 0.0}]
        )
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


def run_phase17(config: Phase17Config) -> Phase17Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    source = _normalize(pd.read_csv(config.adaptive_allocations_path))
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
    phase17_metrics = _metrics(executed, equity, config.initial_capital)
    phase16_equity = pd.read_csv(config.phase16_equity_path)
    phase16_executed = pd.read_csv(config.phase16_executed_path)
    phase16_metrics = _metrics(phase16_executed, phase16_equity, config.initial_capital)
    comparison = pd.DataFrame(
        [
            {"portfolio": "phase16_4", **phase16_metrics},
            {"portfolio": "phase17_4", **phase17_metrics},
        ]
    )
    fold_rows: list[dict[str, float | int]] = []
    fold_column = "phase15_fold" if "phase15_fold" in source else "fold"
    for fold, fold_source in source.groupby(fold_column, sort=True):
        _, fold_candidates = _prepare(fold_source, config)
        fold_executed, _, fold_equity, _ = simulate_portfolio(fold_candidates, portfolio_config)
        fold_rows.append(
            {"fold": int(str(fold)), **_metrics(fold_executed, fold_equity, config.initial_capital)}
        )
    folds = pd.DataFrame(fold_rows)
    positive_fold_rate = float((folds["total_return"] > 0.0).mean()) if not folds.empty else 0.0
    bootstrap = _bootstrap(executed, config.bootstrap_samples, config.random_seed)
    diagnostics = bool(
        not equity.empty
        and abs(float(reconciliation["equity_reconciliation_difference"])) <= 1e-8
        and np.isfinite(list(phase17_metrics.values())).all()
    )
    sharpe_improvement = phase17_metrics["sharpe"] - phase16_metrics["sharpe"]
    pf_improvement = phase17_metrics["profit_factor"] - phase16_metrics["profit_factor"]
    dd_deterioration = phase17_metrics["maximum_drawdown"] - phase16_metrics["maximum_drawdown"]
    approved = bool(
        diagnostics
        and sharpe_improvement >= config.minimum_sharpe_improvement
        and pf_improvement >= config.minimum_profit_factor_improvement
        and dd_deterioration <= config.maximum_drawdown_deterioration
        and positive_fold_rate >= config.minimum_positive_fold_rate
        and float(bootstrap.iloc[0]["probability_positive"]) >= config.minimum_bootstrap_probability
    )
    artifacts = {
        "execution_scores": str(config.output_root / "execution_scores.csv"),
        "liquidity_analysis": str(config.output_root / "liquidity_analysis.csv"),
        "slippage_analysis": str(config.output_root / "slippage_analysis.csv"),
        "capital_efficiency": str(config.output_root / "capital_efficiency.csv"),
        "regime_execution": str(config.output_root / "regime_execution.csv"),
        "phase16_vs_phase17": str(config.output_root / "phase16_vs_phase17.csv"),
        "fold_comparison": str(config.output_root / "fold_comparison.csv"),
        "bootstrap_validation": str(config.output_root / "bootstrap_validation.csv"),
        "executed_trades": str(config.output_root / "phase17_executed_trades.csv"),
        "rejected_signals": str(config.output_root / "phase17_rejected_signals.csv"),
        "equity_curve": str(config.output_root / "phase17_equity_curve.csv"),
        "dashboard": str(config.output_root / "phase17_dashboard.json"),
        "signoff": str(config.output_root / "phase17_final_signoff.json"),
    }
    scored.to_csv(artifacts["execution_scores"], index=False)
    scored.groupby("asset_class", as_index=False).agg(
        trades=("symbol", "size"),
        mean_liquidity=("liquidity_score", "mean"),
        acceptance_rate=("execution_accepted", "mean"),
    ).to_csv(artifacts["liquidity_analysis"], index=False)
    scored[
        [
            "timestamp",
            "symbol",
            "asset_class",
            "incremental_slippage_bps",
            "execution_score",
            "execution_accepted",
        ]
    ].to_csv(artifacts["slippage_analysis"], index=False)
    scored[
        [
            "timestamp",
            "symbol",
            "adaptive_position_fraction",
            "capital_efficiency_multiplier",
            "phase17_position_fraction",
        ]
    ].to_csv(artifacts["capital_efficiency"], index=False)
    scored.groupby("market_regime", as_index=False).agg(
        trades=("symbol", "size"),
        acceptance_rate=("execution_accepted", "mean"),
        mean_execution_score=("execution_score", "mean"),
        mean_slippage_bps=("incremental_slippage_bps", "mean"),
    ).to_csv(artifacts["regime_execution"], index=False)
    comparison.to_csv(artifacts["phase16_vs_phase17"], index=False)
    folds.to_csv(artifacts["fold_comparison"], index=False)
    bootstrap.to_csv(artifacts["bootstrap_validation"], index=False)
    executed.to_csv(artifacts["executed_trades"], index=False)
    rejected.to_csv(artifacts["rejected_signals"], index=False)
    equity.to_csv(artifacts["equity_curve"], index=False)
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "source_candidates": len(source),
        "execution_candidates": len(candidates),
        "executed_trades": len(executed),
        "rejected_trades": len(rejected),
        "phase16_metrics": phase16_metrics,
        "phase17_metrics": phase17_metrics,
        "sharpe_improvement": sharpe_improvement,
        "profit_factor_improvement": pf_improvement,
        "drawdown_deterioration": dd_deterioration,
        "positive_fold_rate": positive_fold_rate,
        "diagnostics_passed": diagnostics,
        "approved_for_phase18_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    signoff = {
        "phase": PHASE,
        "version": VERSION,
        "status": "PHASE17_EXECUTION_AND_CAPITAL_EFFICIENCY_COMPLETE",
        "diagnostics_passed": diagnostics,
        "approved_for_phase18_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "promotion_checks": {
            "sharpe_improvement": sharpe_improvement >= config.minimum_sharpe_improvement,
            "profit_factor_improvement": pf_improvement >= config.minimum_profit_factor_improvement,
            "drawdown_control": dd_deterioration <= config.maximum_drawdown_deterioration,
            "fold_stability": positive_fold_rate >= config.minimum_positive_fold_rate,
            "bootstrap_probability": float(bootstrap.iloc[0]["probability_positive"])
            >= config.minimum_bootstrap_probability,
        },
        "notes": [
            "Execution costs are modeled, not broker fills.",
            "All execution features are available before each trade.",
            "No broker orders are submitted.",
        ],
    }
    Path(artifacts["dashboard"]).write_text(json.dumps(dashboard, indent=2, default=str))
    Path(artifacts["signoff"]).write_text(json.dumps(signoff, indent=2, default=str))
    return Phase17Result(
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
