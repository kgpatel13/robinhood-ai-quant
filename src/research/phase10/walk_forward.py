from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    if frame.empty:
        return {"trades": 0, "average_return": np.nan, "profit_factor": np.nan, "win_rate": np.nan}
    returns = frame["net_return"].astype(float)
    gains = float(returns[returns > 0].sum())
    losses = abs(float(returns[returns < 0].sum()))
    return {
        "trades": len(frame),
        "average_return": float(returns.mean()),
        "profit_factor": gains / losses if losses > 0 else (math.inf if gains > 0 else 0.0),
        "win_rate": float((returns > 0).mean()),
    }


def fixed_split_validation(
    replay: pd.DataFrame,
    thresholds: dict[str, tuple[float, ...]],
    train_end_year: int,
    validation_end_year: int,
    minimum_trades: dict[str, int],
) -> pd.DataFrame:
    frame = replay.copy()
    frame["signal_timestamp"] = pd.to_datetime(frame["signal_timestamp"], utc=True)
    frame["year"] = frame["signal_timestamp"].dt.year
    rows: list[dict[str, object]] = []
    for (asset_class, holding_period), group in frame.groupby(
        ["asset_class", "holding_period"], observed=True
    ):
        asset = str(asset_class)
        threshold_candidates = thresholds[asset]
        train = group[group["year"] <= train_end_year]
        validation = group[
            (group["year"] > train_end_year) & (group["year"] <= validation_end_year)
        ]
        test = group[group["year"] > validation_end_year]
        scored: list[tuple[float, float, float]] = []
        for threshold in threshold_candidates:
            candidate = train[train["opportunity_score"] >= threshold]
            metrics = _metrics(candidate)
            trades = int(metrics["trades"])
            average_return = float(metrics["average_return"])
            profit_factor = float(metrics["profit_factor"])
            if trades >= minimum_trades[asset] and average_return > 0 and profit_factor > 1.0:
                scored.append((threshold, average_return, profit_factor))
        selected = max(scored, key=lambda item: (item[1], item[2]))[0] if scored else np.nan
        splits = (("train", train), ("validation", validation), ("test", test))
        for split_name, split_frame in splits:
            evaluated = (
                split_frame[split_frame["opportunity_score"] >= selected]
                if pd.notna(selected)
                else split_frame.iloc[0:0]
            )
            rows.append(
                {
                    "asset_class": asset,
                    "holding_period": int(str(holding_period)),
                    "split": split_name,
                    "selected_threshold": selected,
                    "train_end_year": train_end_year,
                    "validation_end_year": validation_end_year,
                    **_metrics(evaluated),
                }
            )
    return pd.DataFrame(rows)
