from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FinalPromotionRules:
    minimum_recent_average_return: float = 0.0
    minimum_bootstrap_positive_probability: float = 0.60
    minimum_cross_sectional_top_quantile_lift: float = 0.0
    minimum_feature_stability_fraction: float = 0.50


def label_quality_analysis(replay: pd.DataFrame) -> pd.DataFrame:
    """Summarize return quality using MFE, MAE, payoff efficiency, and tail outcomes."""
    if replay.empty:
        return pd.DataFrame()
    frame = replay.copy()
    frame["downside_risk"] = frame["mae"].astype(float).abs().clip(lower=1e-9)
    frame["return_to_adverse_excursion"] = (
        frame["net_return"].astype(float) / frame["downside_risk"]
    )
    frame["capture_efficiency"] = np.where(
        frame["mfe"].astype(float) > 0,
        frame["net_return"].astype(float) / frame["mfe"].astype(float),
        np.nan,
    )
    rows: list[dict[str, object]] = []
    grouped = frame.groupby(["asset_class", "holding_period", "eligible"], observed=True)
    for raw_key, group in grouped:
        if not isinstance(raw_key, tuple) or len(raw_key) != 3:
            continue
        returns = group["net_return"].astype(float)
        rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "eligible": bool(raw_key[2]),
                "trades": int(len(group)),
                "average_net_return": float(returns.mean()),
                "median_net_return": float(returns.median()),
                "average_mfe": float(group["mfe"].astype(float).mean()),
                "average_mae": float(group["mae"].astype(float).mean()),
                "median_return_to_adverse_excursion": float(
                    group["return_to_adverse_excursion"].median()
                ),
                "median_capture_efficiency": float(group["capture_efficiency"].median()),
                "loss_tail_5pct": float(returns.quantile(0.05)),
                "gain_tail_95pct": float(returns.quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def feature_predictiveness(
    replay: pd.DataFrame,
    feature_columns: Sequence[str],
) -> pd.DataFrame:
    """Measure point-in-time feature rank correlation with future net returns."""
    rows: list[dict[str, object]] = []
    available = [column for column in feature_columns if column in replay.columns]
    for raw_key, group in replay.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        target = pd.to_numeric(group["net_return"], errors="coerce")
        for feature in available:
            values = pd.to_numeric(group[feature], errors="coerce")
            aligned = pd.concat([values, target], axis=1).dropna()
            aligned.columns = ["feature", "target"]
            correlation = math.nan
            if len(aligned) >= 20 and aligned["feature"].nunique() > 1:
                correlation = float(cast(float, aligned.corr(method="spearman").iloc[0, 1]))
            rows.append(
                {
                    "asset_class": str(raw_key[0]),
                    "holding_period": int(str(raw_key[1])),
                    "feature": feature,
                    "observations": int(len(aligned)),
                    "spearman_information_coefficient": correlation,
                    "absolute_information_coefficient": abs(correlation)
                    if math.isfinite(correlation)
                    else math.nan,
                }
            )
    return pd.DataFrame(rows)


def cross_sectional_rank_analysis(replay: pd.DataFrame, quantiles: int = 5) -> pd.DataFrame:
    """Evaluate whether higher same-date scores outperform lower-ranked opportunities."""
    if replay.empty or quantiles < 2:
        return pd.DataFrame()
    frame = replay.copy()
    frame["signal_timestamp"] = pd.to_datetime(frame["signal_timestamp"], utc=True)
    frame["rank_percentile"] = frame.groupby(
        ["asset_class", "holding_period", "signal_timestamp"], observed=True
    )["opportunity_score"].rank(method="average", pct=True)
    frame["rank_quantile"] = np.minimum(
        np.ceil(frame["rank_percentile"].astype(float) * quantiles).astype(int), quantiles
    )
    rows: list[dict[str, object]] = []
    grouped = frame.groupby(["asset_class", "holding_period", "rank_quantile"], observed=True)
    for raw_key, group in grouped:
        if not isinstance(raw_key, tuple) or len(raw_key) != 3:
            continue
        returns = group["net_return"].astype(float)
        rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "rank_quantile": int(str(raw_key[2])),
                "trades": int(len(group)),
                "average_return": float(returns.mean()),
                "median_return": float(returns.median()),
                "win_rate": float((returns > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def time_decay_analysis(replay: pd.DataFrame, recent_years: int = 3) -> pd.DataFrame:
    """Compare eligible-signal performance across calendar years and the recent window."""
    if replay.empty:
        return pd.DataFrame()
    frame = replay[replay["eligible"]].copy()
    frame["year"] = pd.to_datetime(frame["signal_timestamp"], utc=True).dt.year.astype(int)
    rows: list[dict[str, object]] = []
    for raw_key, group in frame.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        maximum_year = int(group["year"].max())
        recent_start = maximum_year - recent_years + 1
        for label, sample in (
            ("all_history", group),
            (f"recent_{recent_years}y", group[group["year"] >= recent_start]),
        ):
            returns = sample["net_return"].astype(float)
            rows.append(
                {
                    "asset_class": str(raw_key[0]),
                    "holding_period": int(str(raw_key[1])),
                    "window": label,
                    "start_year": int(sample["year"].min()) if len(sample) else recent_start,
                    "end_year": int(sample["year"].max()) if len(sample) else maximum_year,
                    "trades": int(len(sample)),
                    "average_return": float(returns.mean()) if len(sample) else math.nan,
                    "median_return": float(returns.median()) if len(sample) else math.nan,
                    "win_rate": float((returns > 0).mean()) if len(sample) else math.nan,
                }
            )
    return pd.DataFrame(rows)


def bootstrap_confidence(
    replay: pd.DataFrame,
    samples: int = 1000,
    seed: int = 10,
) -> pd.DataFrame:
    """Estimate uncertainty of eligible-signal mean returns using deterministic bootstrap."""
    if replay.empty or samples < 100:
        return pd.DataFrame()
    generator = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    eligible = replay[replay["eligible"]]
    for raw_key, group in eligible.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        returns = group["net_return"].astype(float).dropna().to_numpy()
        if len(returns) < 2:
            continue
        indices = generator.integers(0, len(returns), size=(samples, len(returns)))
        means = returns[indices].mean(axis=1)
        rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "trades": int(len(returns)),
                "observed_average_return": float(returns.mean()),
                "bootstrap_mean_return": float(means.mean()),
                "confidence_lower_95": float(np.quantile(means, 0.025)),
                "confidence_upper_95": float(np.quantile(means, 0.975)),
                "probability_mean_positive": float((means > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def feature_stability(feature_ic: pd.DataFrame) -> pd.DataFrame:
    if feature_ic.empty:
        return pd.DataFrame()
    frame = feature_ic.copy()
    frame["stable_predictive"] = (frame["observations"].astype(int) >= 20) & (
        frame["absolute_information_coefficient"].fillna(0).astype(float) >= 0.02
    )
    rows: list[dict[str, object]] = []
    for raw_key, group in frame.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "features_evaluated": int(len(group)),
                "predictive_features": int(group["stable_predictive"].sum()),
                "predictive_feature_fraction": float(group["stable_predictive"].mean()),
                "maximum_absolute_information_coefficient": float(
                    group["absolute_information_coefficient"].max()
                ),
            }
        )
    return pd.DataFrame(rows)


def final_promotion_decisions(
    base_decisions: pd.DataFrame,
    decay: pd.DataFrame,
    bootstrap: pd.DataFrame,
    rank_analysis: pd.DataFrame,
    stability: pd.DataFrame,
    rules: FinalPromotionRules,
) -> pd.DataFrame:
    if base_decisions.empty:
        return pd.DataFrame()
    recent = decay[decay["window"].astype(str).str.startswith("recent_")][
        ["asset_class", "holding_period", "average_return"]
    ].rename(columns={"average_return": "recent_average_return"})
    confidence = bootstrap[["asset_class", "holding_period", "probability_mean_positive"]]
    feature = stability[["asset_class", "holding_period", "predictive_feature_fraction"]]
    rank_rows: list[dict[str, object]] = []
    for raw_key, group in rank_analysis.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2 or group.empty:
            continue
        ordered = group.sort_values("rank_quantile")
        rank_rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "top_quantile_lift": float(
                    ordered.iloc[-1]["average_return"] - ordered.iloc[0]["average_return"]
                ),
            }
        )
    rank_lift = pd.DataFrame(rank_rows)
    result = base_decisions.merge(recent, on=["asset_class", "holding_period"], how="left")
    result = result.merge(confidence, on=["asset_class", "holding_period"], how="left")
    result = result.merge(rank_lift, on=["asset_class", "holding_period"], how="left")
    result = result.merge(feature, on=["asset_class", "holding_period"], how="left")
    result["advanced_validation_passed"] = (
        (result["recent_average_return"].fillna(-math.inf) > rules.minimum_recent_average_return)
        & (
            result["probability_mean_positive"].fillna(0)
            >= rules.minimum_bootstrap_positive_probability
        )
        & (
            result["top_quantile_lift"].fillna(-math.inf)
            > rules.minimum_cross_sectional_top_quantile_lift
        )
        & (
            result["predictive_feature_fraction"].fillna(0)
            >= rules.minimum_feature_stability_fraction
        )
    )
    result["final_promoted"] = result["promoted"].astype(bool) & result[
        "advanced_validation_passed"
    ].astype(bool)
    result["final_decision"] = np.where(
        result["final_promoted"], "PROMOTE_TO_PHASE11_PAPER", "REJECT_OR_RESEARCH"
    )
    return result


def final_research_signoff(
    decisions: pd.DataFrame,
    leakage: pd.DataFrame,
    version: str,
    data_cutoff: str,
) -> dict[str, Any]:
    leakage_passed = bool(leakage["passed"].all()) if not leakage.empty else False
    approved = (
        decisions[decisions["final_promoted"]][["asset_class", "holding_period"]].to_dict(
            orient="records"
        )
        if not decisions.empty and leakage_passed
        else []
    )
    return {
        "phase": "10.4.0",
        "version": version,
        "data_cutoff": data_cutoff,
        "leakage_audit_passed": leakage_passed,
        "approved_for_phase11_paper_trading": approved,
        "production_live_trading_approved": False,
        "phase10_series_complete": True,
        "status": "PHASE10_COMPLETE" if leakage_passed else "BLOCKED_BY_AUDIT",
        "notes": [
            "Phase 10.x research and robustness validation is complete.",
            "Promotion requires both rolling out-of-sample and advanced validation gates.",
            "No live trading is authorized by this sign-off.",
        ],
    }
