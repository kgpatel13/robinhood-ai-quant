from __future__ import annotations

import math
from typing import cast

import numpy as np
import pandas as pd


def _profit_factor(returns: pd.Series) -> float:
    gains = float(returns[returns > 0].sum())
    losses = abs(float(returns[returns < 0].sum()))
    return gains / losses if losses > 0 else (math.inf if gains > 0 else 0.0)


def _max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def summarize_group(group: pd.DataFrame) -> pd.Series:
    returns = group["net_return"].astype(float)
    return_values = [float(value) for value in returns.tolist()]
    standard_deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    metrics: dict[str, object] = {
        "trades": len(group),
        "win_rate": float((returns > 0).mean()),
        "average_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "total_compounded_return": math.prod(1.0 + value for value in return_values) - 1.0,
        "profit_factor": _profit_factor(returns),
        "return_to_risk": (
            float(returns.mean() / standard_deviation) if standard_deviation > 0 else 0.0
        ),
        "maximum_drawdown": _max_drawdown(returns),
        "average_mfe": float(group["mfe"].mean()),
        "average_mae": float(group["mae"].mean()),
        "target_rate": float((group["exit_reason"] == "target").mean()),
        "stop_rate": float((group["exit_reason"] == "stop").mean()),
        "average_bars_held": float(group["bars_held"].mean()),
    }
    return pd.Series(metrics, dtype="object")


def aggregate(replay: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if replay.empty:
        return pd.DataFrame(columns=[*group_columns, "trades"])

    rows: list[dict[str, object]] = []
    grouped = replay.groupby(group_columns, observed=True, dropna=False)
    for raw_key, group in grouped:
        key_values = raw_key if isinstance(raw_key, tuple) else (raw_key,)
        row: dict[str, object] = dict(zip(group_columns, key_values, strict=True))
        metrics = cast(dict[str, object], summarize_group(group).to_dict())
        row.update(metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def _parse_group_key(key: object) -> tuple[str, int]:
    if not isinstance(key, tuple) or len(key) != 2:
        raise ValueError(f"Expected a two-item grouping key, received {key!r}")
    return str(key[0]), int(str(key[1]))


def score_monotonicity(score_bands: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["asset_class", "holding_period"]
    for key, group in score_bands.groupby(keys, observed=True):
        asset_class, holding_period = _parse_group_key(key)
        ordered = group.sort_values("band_lower")
        valid = ordered[ordered["trades"] >= 5]
        correlation = np.nan
        if len(valid) >= 2:
            value = valid["band_lower"].corr(valid["average_return"], method="spearman")
            correlation = float(value) if pd.notna(value) else np.nan
        rows.append(
            {
                "asset_class": asset_class,
                "holding_period": holding_period,
                "spearman_score_return": correlation,
                "bands_evaluated": len(valid),
            }
        )
    return pd.DataFrame(rows)


def threshold_recommendations(
    score_bands: pd.DataFrame,
    minimum_trades: dict[str, int],
) -> pd.DataFrame:
    candidates: list[dict[str, object]] = []
    groups = score_bands.groupby(["asset_class", "holding_period"], observed=True)
    for key, group in groups:
        asset_class, holding_period = _parse_group_key(key)
        floor = minimum_trades[asset_class]
        qualified = group[
            (group["trades"] >= floor)
            & (group["average_return"] > 0)
            & (group["profit_factor"] > 1.0)
        ]
        if qualified.empty:
            candidates.append(
                {
                    "asset_class": asset_class,
                    "holding_period": holding_period,
                    "recommended_threshold": np.nan,
                    "status": "insufficient_positive_evidence",
                    "trades": 0,
                    "average_return": np.nan,
                    "profit_factor": np.nan,
                }
            )
            continue
        best = qualified.sort_values(["return_to_risk", "average_return"], ascending=False).iloc[0]
        candidates.append(
            {
                "asset_class": asset_class,
                "holding_period": holding_period,
                "recommended_threshold": float(best["band_lower"]),
                "status": "research_candidate",
                "trades": int(best["trades"]),
                "average_return": float(best["average_return"]),
                "profit_factor": float(best["profit_factor"]),
            }
        )
    return pd.DataFrame(candidates)
