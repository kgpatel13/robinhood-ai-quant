from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PromotionRules:
    minimum_profitable_window_fraction: float = 0.60
    minimum_median_profit_factor: float = 1.10
    minimum_median_average_return: float = 0.0
    minimum_test_trades: int = 100
    maximum_threshold_range: float = 15.0


def _trade_metrics(
    frame: pd.DataFrame, return_column: str = "net_return"
) -> dict[str, float | int]:
    if frame.empty:
        return {
            "trades": 0,
            "average_return": math.nan,
            "median_return": math.nan,
            "profit_factor": math.nan,
            "win_rate": math.nan,
        }
    returns = frame[return_column].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return {
            "trades": 0,
            "average_return": math.nan,
            "median_return": math.nan,
            "profit_factor": math.nan,
            "win_rate": math.nan,
        }
    gains = float(returns[returns > 0].sum())
    losses = abs(float(returns[returns < 0].sum()))
    return {
        "trades": int(len(returns)),
        "average_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "profit_factor": gains / losses if losses > 0 else (math.inf if gains > 0 else 0.0),
        "win_rate": float((returns > 0).mean()),
    }


def rolling_walk_forward_validation(
    replay: pd.DataFrame,
    thresholds: Mapping[str, Sequence[float]],
    minimum_trades: Mapping[str, int],
    train_years: int = 5,
    validation_years: int = 1,
    test_years: int = 1,
    step_years: int = 1,
) -> pd.DataFrame:
    """Select a threshold using past data and evaluate successive unseen test years."""
    frame = replay.copy()
    frame["signal_timestamp"] = pd.to_datetime(frame["signal_timestamp"], utc=True)
    frame["year"] = frame["signal_timestamp"].dt.year.astype(int)
    rows: list[dict[str, object]] = []
    for raw_key, group in frame.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        asset = str(raw_key[0])
        holding_period = int(str(raw_key[1]))
        years = sorted(int(value) for value in group["year"].unique())
        if len(years) < train_years + validation_years + test_years:
            continue
        first_test_start = years[0] + train_years + validation_years
        last_year = years[-1]
        for test_start in range(first_test_start, last_year - test_years + 2, step_years):
            train_start = test_start - validation_years - train_years
            train_end = test_start - validation_years - 1
            validation_start = train_end + 1
            validation_end = test_start - 1
            test_end = test_start + test_years - 1
            train = group[(group["year"] >= train_start) & (group["year"] <= train_end)]
            validation = group[
                (group["year"] >= validation_start) & (group["year"] <= validation_end)
            ]
            test = group[(group["year"] >= test_start) & (group["year"] <= test_end)]
            if train.empty or validation.empty or test.empty:
                continue
            candidates: list[tuple[float, float, float, float]] = []
            for threshold in thresholds.get(asset, ()):
                train_eval = train[train["opportunity_score"] >= float(threshold)]
                validation_eval = validation[validation["opportunity_score"] >= float(threshold)]
                train_metrics = _trade_metrics(train_eval)
                validation_metrics = _trade_metrics(validation_eval)
                if (
                    int(train_metrics["trades"]) >= int(minimum_trades.get(asset, 1))
                    and int(validation_metrics["trades"])
                    >= max(10, int(minimum_trades.get(asset, 1)) // 4)
                    and float(train_metrics["profit_factor"]) > 1.0
                    and float(validation_metrics["profit_factor"]) > 1.0
                    and float(validation_metrics["average_return"]) > 0
                ):
                    candidates.append(
                        (
                            float(threshold),
                            float(validation_metrics["average_return"]),
                            float(validation_metrics["profit_factor"]),
                            float(train_metrics["profit_factor"]),
                        )
                    )
            selected = (
                max(candidates, key=lambda item: (item[1], item[2], item[3]))[0]
                if candidates
                else math.nan
            )
            evaluated = (
                test[test["opportunity_score"] >= selected]
                if not math.isnan(selected)
                else test.iloc[0:0]
            )
            rows.append(
                {
                    "asset_class": asset,
                    "holding_period": holding_period,
                    "train_start_year": train_start,
                    "train_end_year": train_end,
                    "validation_start_year": validation_start,
                    "validation_end_year": validation_end,
                    "test_start_year": test_start,
                    "test_end_year": test_end,
                    "selected_threshold": selected,
                    **_trade_metrics(evaluated),
                }
            )
    return pd.DataFrame(rows)


def window_stability(rolling: pd.DataFrame) -> pd.DataFrame:
    if rolling.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for raw_key, group in rolling.groupby(["asset_class", "holding_period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        valid = group[group["trades"].astype(int) > 0].copy()
        profitable = valid[valid["average_return"].astype(float) > 0]
        thresholds = valid["selected_threshold"].dropna().astype(float)
        rows.append(
            {
                "asset_class": str(raw_key[0]),
                "holding_period": int(str(raw_key[1])),
                "test_windows": int(len(valid)),
                "profitable_windows": int(len(profitable)),
                "profitable_window_fraction": float(len(profitable) / len(valid))
                if len(valid)
                else 0.0,
                "median_test_average_return": float(valid["average_return"].median())
                if len(valid)
                else math.nan,
                "median_test_profit_factor": float(valid["profit_factor"].median())
                if len(valid)
                else math.nan,
                "worst_test_average_return": float(valid["average_return"].min())
                if len(valid)
                else math.nan,
                "total_test_trades": int(valid["trades"].sum()) if len(valid) else 0,
                "minimum_threshold": float(thresholds.min()) if len(thresholds) else math.nan,
                "maximum_threshold": float(thresholds.max()) if len(thresholds) else math.nan,
                "threshold_range": float(thresholds.max() - thresholds.min())
                if len(thresholds)
                else math.nan,
            }
        )
    return pd.DataFrame(rows)


def transaction_cost_stress(
    replay: pd.DataFrame,
    incremental_cost_bps: Mapping[str, Mapping[str, float]],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for raw_key, group in replay[replay["eligible"]].groupby(
        ["asset_class", "holding_period"], observed=True
    ):
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        asset = str(raw_key[0])
        holding_period = int(str(raw_key[1]))
        for scenario, bps in incremental_cost_bps.get(asset, {}).items():
            adjusted = group.copy()
            adjusted["stressed_return"] = (
                adjusted["net_return"].astype(float) - float(bps) / 10_000.0
            )
            rows.append(
                {
                    "asset_class": asset,
                    "holding_period": holding_period,
                    "cost_scenario": str(scenario),
                    "incremental_round_trip_bps": float(bps),
                    **_trade_metrics(adjusted, "stressed_return"),
                }
            )
    return pd.DataFrame(rows)


def benchmark_comparison(
    daily_equity: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark_symbols: Mapping[str, str],
) -> pd.DataFrame:
    if daily_equity.empty or prices.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for raw_key, group in daily_equity.groupby(
        ["asset_class", "holding_period", "threshold"], observed=True
    ):
        if not isinstance(raw_key, tuple) or len(raw_key) != 3:
            continue
        asset = str(raw_key[0])
        benchmark = benchmark_symbols.get(asset)
        if benchmark is None or benchmark not in prices.columns:
            continue
        ordered = group.sort_values("timestamp").copy()
        ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
        equity = ordered.set_index("timestamp")["equity"].astype(float)
        benchmark_series = prices[benchmark].dropna().astype(float)
        common = equity.index.intersection(benchmark_series.index)
        if len(common) < 2:
            continue
        strategy_return = float(equity.loc[common[-1]] / equity.loc[common[0]] - 1.0)
        benchmark_return = float(
            benchmark_series.loc[common[-1]] / benchmark_series.loc[common[0]] - 1.0
        )
        strategy_daily = equity.loc[common].pct_change().dropna()
        benchmark_daily = benchmark_series.loc[common].pct_change().dropna()
        aligned = pd.concat([strategy_daily, benchmark_daily], axis=1).dropna()
        aligned.columns = ["strategy", "benchmark"]
        tracking = (
            aligned["strategy"] - aligned["benchmark"]
            if not aligned.empty
            else pd.Series(dtype=float)
        )
        information_ratio = (
            float(tracking.mean() / tracking.std(ddof=0) * math.sqrt(252.0))
            if len(tracking) > 1 and float(tracking.std(ddof=0)) > 0
            else math.nan
        )
        rows.append(
            {
                "asset_class": asset,
                "holding_period": int(str(raw_key[1])),
                "threshold": float(str(raw_key[2])),
                "benchmark_symbol": benchmark,
                "strategy_total_return": strategy_return,
                "benchmark_total_return": benchmark_return,
                "excess_total_return": strategy_return - benchmark_return,
                "correlation": (
                    float(cast(float, aligned.corr().iloc[0, 1])) if len(aligned) > 1 else math.nan
                ),
                "information_ratio": information_ratio,
            }
        )
    return pd.DataFrame(rows)


def leakage_audit(replay: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    signal = pd.to_datetime(replay["signal_timestamp"], utc=True)
    entry = pd.to_datetime(replay["entry_timestamp"], utc=True)
    exit_time = pd.to_datetime(replay["exit_timestamp"], utc=True)
    checks.append(
        {
            "check": "entry_after_signal",
            "passed": bool((entry > signal).all()),
            "violations": int((entry <= signal).sum()),
        }
    )
    checks.append(
        {
            "check": "exit_not_before_entry",
            "passed": bool((exit_time >= entry).all()),
            "violations": int((exit_time < entry).sum()),
        }
    )
    numeric = [
        "entry_price",
        "exit_price",
        "stop_price",
        "target_price",
        "opportunity_score",
        "net_return",
    ]
    for column in numeric:
        values = pd.to_numeric(replay[column], errors="coerce")
        violations = int((~np.isfinite(values)).sum())
        checks.append(
            {"check": f"finite_{column}", "passed": violations == 0, "violations": violations}
        )
    score = pd.to_numeric(replay["opportunity_score"], errors="coerce")
    score_violations = int(((score < 0) | (score > 100)).sum())
    checks.append(
        {
            "check": "score_range_0_100",
            "passed": score_violations == 0,
            "violations": score_violations,
        }
    )
    return pd.DataFrame(checks)


def promotion_decisions(stability: pd.DataFrame, rules: PromotionRules) -> pd.DataFrame:
    if stability.empty:
        return pd.DataFrame()
    frame = stability.copy()
    frame["promoted"] = (
        (
            frame["profitable_window_fraction"].astype(float)
            >= rules.minimum_profitable_window_fraction
        )
        & (frame["median_test_profit_factor"].astype(float) >= rules.minimum_median_profit_factor)
        & (frame["median_test_average_return"].astype(float) > rules.minimum_median_average_return)
        & (frame["total_test_trades"].astype(int) >= rules.minimum_test_trades)
        & (frame["threshold_range"].fillna(math.inf).astype(float) <= rules.maximum_threshold_range)
    )
    frame["decision"] = np.where(frame["promoted"], "PROMOTE_TO_PAPER", "REJECT_OR_RESEARCH")
    return frame


def research_signoff(
    decisions: pd.DataFrame,
    leakage: pd.DataFrame,
    version: str,
    data_cutoff: str,
) -> dict[str, Any]:
    leakage_passed = bool(leakage["passed"].all()) if not leakage.empty else False
    approved = (
        decisions[decisions["promoted"]][["asset_class", "holding_period"]].to_dict(
            orient="records"
        )
        if not decisions.empty and leakage_passed
        else []
    )
    return {
        "phase": "10.2.0",
        "version": version,
        "data_cutoff": data_cutoff,
        "leakage_audit_passed": leakage_passed,
        "approved_for_phase11_paper_trading": approved,
        "production_live_trading_approved": False,
        "status": "RESEARCH_SIGNOFF_COMPLETE" if leakage_passed else "BLOCKED_BY_AUDIT",
        "notes": [
            "Approval applies to paper trading only.",
            "Thresholds must be selected only from prior rolling windows.",
            "Live trading requires Phase 11 execution validation and additional risk controls.",
        ],
    }
