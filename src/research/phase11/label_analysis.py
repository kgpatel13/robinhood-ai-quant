from __future__ import annotations

import math
from numbers import Integral
from typing import cast

import numpy as np
import pandas as pd

LABEL_COLUMNS = (
    "forward_return",
    "net_forward_return",
    "mfe",
    "mae",
    "positive_return_label",
    "risk_adjusted_label",
)


def _as_holding_period(value: object) -> int:
    """Convert a validated pandas grouping value into an integer horizon."""
    if isinstance(value, Integral):
        return int(value)

    if isinstance(value, float) and value.is_integer():
        return int(value)

    raise TypeError(f"Invalid holding period: {value!r}")


def deterministic_label_sample(frame: pd.DataFrame, maximum_rows: int, seed: int) -> pd.DataFrame:
    """Sample complete timestamp-symbol events without splitting horizon panels."""
    if len(frame) <= maximum_rows:
        return frame.copy()

    event_columns = ["timestamp", "symbol"]
    event_sizes = (
        frame.groupby(event_columns, sort=False, dropna=False)
        .size()
        .rename("rows")
        .reset_index()
        .sample(frac=1.0, random_state=seed)
        .reset_index(drop=True)
    )
    selected_events = event_sizes.loc[event_sizes["rows"].cumsum() <= maximum_rows, event_columns]
    if selected_events.empty:
        selected_events = event_sizes.loc[[0], event_columns]

    sampled = frame.merge(selected_events, on=event_columns, how="inner", validate="many_to_one")
    return sampled.sort_values(["timestamp", "symbol", "holding_period"]).reset_index(drop=True)


def _entropy(rate: float) -> float:
    if rate <= 0.0 or rate >= 1.0:
        return 0.0
    return float(-(rate * math.log2(rate) + (1.0 - rate) * math.log2(1.0 - rate)))


def label_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for horizon, group in frame.groupby("holding_period", sort=True):
        net = pd.to_numeric(group["net_forward_return"], errors="coerce").dropna()
        positive_rate = float(pd.to_numeric(group["positive_return_label"], errors="coerce").mean())
        rows.append(
            {
                "holding_period": _as_holding_period(horizon),
                "rows": int(len(group)),
                "symbols": int(group["symbol"].nunique()),
                "asset_classes": int(group["asset_class"].nunique()),
                "positive_rate": positive_rate,
                "label_entropy": _entropy(positive_rate),
                "mean_net_return": float(net.mean()),
                "median_net_return": float(net.median()),
                "net_return_std": float(net.std(ddof=0)),
                "mean_risk_adjusted_label": float(
                    pd.to_numeric(group["risk_adjusted_label"], errors="coerce").mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def class_balance(frame: pd.DataFrame) -> pd.DataFrame:
    result = (
        frame.groupby("holding_period", sort=True)["positive_return_label"]
        .agg(rows="size", positive_rate="mean")
        .reset_index()
    )
    result["negative_rate"] = 1.0 - result["positive_rate"]
    result["minority_rate"] = result[["positive_rate", "negative_rate"]].min(axis=1)
    result["entropy"] = result["positive_rate"].map(_entropy)
    return result


def return_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for horizon, group in frame.groupby("holding_period", sort=True):
        values = pd.to_numeric(group["net_forward_return"], errors="coerce").dropna()
        quantiles = values.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
        rows.append(
            {
                "holding_period": _as_holding_period(horizon),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "p01": float(quantiles.loc[0.01]),
                "p05": float(quantiles.loc[0.05]),
                "p25": float(quantiles.loc[0.25]),
                "median": float(quantiles.loc[0.5]),
                "p75": float(quantiles.loc[0.75]),
                "p95": float(quantiles.loc[0.95]),
                "p99": float(quantiles.loc[0.99]),
                "skewness": cast(float, values.skew()),
                "kurtosis": cast(float, values.kurt()),
            }
        )
    return pd.DataFrame(rows)


def risk_reward_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for horizon, group in frame.groupby("holding_period", sort=True):
        mfe = pd.to_numeric(group["mfe"], errors="coerce")
        mae = pd.to_numeric(group["mae"], errors="coerce").abs()
        reward_risk = mfe / mae.replace(0.0, np.nan)
        rows.append(
            {
                "holding_period": _as_holding_period(horizon),
                "mean_mfe": float(mfe.mean()),
                "median_mfe": float(mfe.median()),
                "mean_abs_mae": float(mae.mean()),
                "median_abs_mae": float(mae.median()),
                "median_reward_risk": float(reward_risk.median()),
                "positive_risk_adjusted_rate": float(
                    (pd.to_numeric(group["risk_adjusted_label"], errors="coerce") > 0.0).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def label_noise(frame: pd.DataFrame, extreme_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for horizon, group in frame.groupby("holding_period", sort=True):
        net = pd.to_numeric(group["net_forward_return"], errors="coerce")
        binary = pd.to_numeric(group["positive_return_label"], errors="coerce")
        near_zero = net.abs() <= 0.001
        mismatch = binary.ne((net > 0.0).astype(int))
        rows.append(
            {
                "holding_period": _as_holding_period(horizon),
                "near_zero_fraction": float(near_zero.mean()),
                "extreme_return_fraction": float((net.abs() >= extreme_threshold).mean()),
                "binary_label_mismatch_fraction": float(mismatch.mean()),
                "sign_conflict_fraction": float(
                    (
                        (net > 0.0)
                        & (pd.to_numeric(group["risk_adjusted_label"], errors="coerce") <= 0.0)
                    ).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def label_overlap(frame: pd.DataFrame) -> pd.DataFrame:
    key = ["timestamp", "symbol"]
    pivot = frame.pivot_table(
        index=key, columns="holding_period", values="positive_return_label", aggfunc="first"
    )
    horizons = sorted(int(value) for value in pivot.columns)
    rows: list[dict[str, object]] = []
    for index, left in enumerate(horizons):
        for right in horizons[index + 1 :]:
            pair = pivot[[left, right]].dropna()
            rows.append(
                {
                    "left_horizon": left,
                    "right_horizon": right,
                    "rows": int(len(pair)),
                    "agreement_rate": float((pair[left] == pair[right]).mean())
                    if len(pair)
                    else math.nan,
                    "correlation": float(pair[left].corr(pair[right]))
                    if len(pair) > 1
                    else math.nan,
                }
            )
    return pd.DataFrame(rows)


def grouped_quality(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (horizon, group_name), group in frame.groupby(["holding_period", group_column], sort=True):
        net = pd.to_numeric(group["net_forward_return"], errors="coerce")
        rows.append(
            {
                "holding_period": _as_holding_period(horizon),
                group_column: str(group_name),
                "rows": int(len(group)),
                "positive_rate": float(
                    pd.to_numeric(group["positive_return_label"], errors="coerce").mean()
                ),
                "mean_net_return": float(net.mean()),
                "median_net_return": float(net.median()),
                "net_return_std": float(net.std(ddof=0)),
            }
        )
    return pd.DataFrame(rows)


def horizon_quality_index(
    summary: pd.DataFrame,
    noise: pd.DataFrame,
    asset: pd.DataFrame,
    regime: pd.DataFrame,
    minimum_rows: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, record in summary.iterrows():
        horizon = _as_holding_period(record["holding_period"])
        positive_rate = float(record["positive_rate"])
        balance_score = max(0.0, 1.0 - abs(positive_rate - 0.5) / 0.5)
        sample_score = min(1.0, float(record["rows"]) / float(minimum_rows))
        std = float(record["net_return_std"])
        mean_net_return = float(record["mean_net_return"])
        signal_score = min(1.0, max(0.0, mean_net_return) / std * 10.0) if std > 0 else 0.0
        noise_row = noise.loc[noise["holding_period"] == horizon].iloc[0]
        noise_score = max(
            0.0,
            1.0
            - float(noise_row["near_zero_fraction"])
            - float(noise_row["sign_conflict_fraction"]),
        )
        asset_rates = asset.loc[asset["holding_period"] == horizon, "positive_rate"]
        regime_rates = regime.loc[regime["holding_period"] == horizon, "positive_rate"]
        asset_score = max(
            0.0, 1.0 - float(asset_rates.std(ddof=0) if len(asset_rates) > 1 else 0.0) * 4.0
        )
        regime_score = max(
            0.0, 1.0 - float(regime_rates.std(ddof=0) if len(regime_rates) > 1 else 0.0) * 4.0
        )
        quality = (
            0.20 * balance_score
            + 0.15 * sample_score
            + 0.15 * signal_score
            + 0.20 * noise_score
            + 0.15 * asset_score
            + 0.15 * regime_score
        )
        rows.append(
            {
                "holding_period": horizon,
                "balance_score": balance_score,
                "sample_score": sample_score,
                "signal_to_noise_score": signal_score,
                "noise_score": noise_score,
                "asset_consistency_score": asset_score,
                "regime_stability_score": regime_score,
                "label_quality_index": quality,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values("label_quality_index", ascending=False)
        .reset_index(drop=True)
    )


def leakage_checks(frame: pd.DataFrame) -> pd.DataFrame:
    checks = [
        (
            "binary_matches_net_return_sign",
            bool(
                (
                    pd.to_numeric(frame["positive_return_label"], errors="coerce")
                    == (pd.to_numeric(frame["net_forward_return"], errors="coerce") > 0.0).astype(
                        int
                    )
                ).all()
            ),
        ),
        (
            "exit_not_before_entry",
            bool(
                (
                    pd.to_datetime(frame["exit_timestamp"])
                    >= pd.to_datetime(frame["entry_timestamp"])
                ).all()
            ),
        ),
        (
            "entry_after_signal",
            bool(
                (
                    pd.to_datetime(frame["entry_timestamp"]) > pd.to_datetime(frame["timestamp"])
                ).all()
            ),
        ),
        (
            "finite_labels",
            bool(
                np.isfinite(
                    frame[list(LABEL_COLUMNS)]
                    .apply(pd.to_numeric, errors="coerce")
                    .to_numpy(dtype=float)
                ).all()
            ),
        ),
    ]
    return pd.DataFrame([{"check": name, "passed": passed} for name, passed in checks])
