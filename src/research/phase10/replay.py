from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from src.research.phase9.scoring import ScoreBreakdown, score_opportunity
from src.research.phase10.features import classify_regime
from src.research.phase10.models import AssetClass, ReplayProfile

FEATURE_COLUMNS = (
    "trend_fast_slow",
    "trend_50_200",
    "momentum_5",
    "momentum_21",
    "relative_volume",
    "annualized_volatility",
    "rsi_14",
    "breakout_20",
)


def _round_trip_cost(profile: ReplayProfile) -> float:
    return (2.0 * profile.slippage_bps + profile.spread_bps + 2.0 * profile.fee_bps) / 10_000.0


def _score_row(row: pd.Series, asset_class: AssetClass) -> ScoreBreakdown:
    features = {column: float(row[column]) for column in FEATURE_COLUMNS}
    scoring_asset = "stock" if asset_class == "etf" else asset_class
    return score_opportunity(features, scoring_asset)


def _barrier_outcome(
    future: pd.DataFrame,
    entry: float,
    atr: float,
    profile: ReplayProfile,
    same_bar_policy: str,
) -> tuple[float, str, int, float, float]:
    stop = entry - profile.stop_atr_multiple * atr
    target = entry + profile.target_atr_multiple * atr
    max_high = entry
    min_low = entry
    for offset, (_, bar) in enumerate(future.iterrows(), start=1):
        high = float(bar["high"])
        low = float(bar["low"])
        max_high = max(max_high, high)
        min_low = min(min_low, low)
        hit_stop = low <= stop
        hit_target = high >= target
        if hit_stop and hit_target:
            if same_bar_policy == "optimistic":
                exit_price, reason = target, "target"
            elif same_bar_policy == "ambiguous":
                exit_price, reason = entry, "ambiguous"
            else:
                exit_price, reason = stop, "stop"
            return exit_price, reason, offset, max_high, min_low
        if hit_stop:
            return stop, "stop", offset, max_high, min_low
        if hit_target:
            return target, "target", offset, max_high, min_low
    return float(future["close"].iloc[-1]), "time", len(future), max_high, min_low


def replay_symbol(
    features: pd.DataFrame,
    asset_class: AssetClass,
    profile: ReplayProfile,
    warmup_bars: int,
    signal_stride: int,
    same_bar_policy: str,
    include_below_threshold: bool,
) -> pd.DataFrame:
    maximum_horizon = max(profile.holding_periods)
    rows: list[dict[str, object]] = []
    last_signal_index = len(features) - maximum_horizon - 1
    for index in range(warmup_bars - 1, last_signal_index + 1, signal_stride):
        row = features.iloc[index]
        if row[list(FEATURE_COLUMNS) + ["atr", "market_sma_200", "market_return_63"]].isna().any():
            continue
        score = _score_row(row, asset_class)
        if not include_below_threshold and score.total < profile.entry_score:
            continue
        entry_index = index + 1
        entry = float(features.iloc[entry_index]["open"])
        atr = float(row["atr"])
        if entry <= 0 or atr <= 0:
            continue
        base = {
            "symbol": str(row["symbol"]),
            "asset_class": asset_class,
            "signal_timestamp": row["timestamp"],
            "entry_timestamp": features.iloc[entry_index]["timestamp"],
            "signal_close": float(row["price"]),
            "entry_price": entry,
            "atr": atr,
            "opportunity_score": score.total,
            "threshold": profile.entry_score,
            "eligible": score.total >= profile.entry_score,
            "regime": classify_regime(row),
            **{column: float(row[column]) for column in FEATURE_COLUMNS},
            **{f"{key}_score": value for key, value in asdict(score).items() if key != "total"},
        }
        for horizon in profile.holding_periods:
            future = features.iloc[entry_index : entry_index + horizon]
            exit_price, reason, bars_held, max_high, min_low = _barrier_outcome(
                future, entry, atr, profile, same_bar_policy
            )
            gross_return = exit_price / entry - 1.0
            net_return = gross_return - _round_trip_cost(profile)
            rows.append(
                {
                    **base,
                    "holding_period": horizon,
                    "exit_timestamp": future.iloc[bars_held - 1]["timestamp"],
                    "exit_price": exit_price,
                    "exit_reason": reason,
                    "bars_held": bars_held,
                    "gross_return": gross_return,
                    "net_return": net_return,
                    "mfe": max_high / entry - 1.0,
                    "mae": min_low / entry - 1.0,
                    "stop_price": entry - profile.stop_atr_multiple * atr,
                    "target_price": entry + profile.target_atr_multiple * atr,
                }
            )
    return pd.DataFrame(rows)


def assign_score_band(scores: pd.Series, bands: tuple[float, ...]) -> pd.Series:
    labels = [f"{bands[i]:g}-{bands[i + 1]:g}" for i in range(len(bands) - 1)]
    return pd.cut(scores, bins=list(bands), labels=labels, right=False, include_lowest=True)
