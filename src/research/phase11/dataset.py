from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase11.models import Phase11Config

KEY_COLUMNS = ("timestamp", "symbol", "asset_class", "holding_period")
LABEL_COLUMNS = (
    "forward_return",
    "net_forward_return",
    "mfe",
    "mae",
    "positive_return_label",
    "risk_adjusted_label",
)


def round_trip_cost(config: Phase11Config) -> float:
    return (2.0 * config.slippage_bps + config.spread_bps + 2.0 * config.fee_bps) / 10_000.0


def build_symbol_dataset(
    features: pd.DataFrame,
    asset_class: str,
    config: Phase11Config,
) -> pd.DataFrame:
    maximum_horizon = max(config.holding_periods)
    rows: list[dict[str, object]] = []
    last_index = len(features) - maximum_horizon - 1
    cost = round_trip_cost(config)
    for index in range(config.warmup_bars - 1, last_index + 1, config.observation_stride):
        current = features.iloc[index]
        if current[list(FEATURE_COLUMNS)].isna().any() or str(current["regime"]) == "unknown":
            continue
        entry_index = index + 1
        entry = float(features.iloc[entry_index]["open"])
        if not np.isfinite(entry) or entry <= 0:
            continue
        base: dict[str, object] = {
            "timestamp": current["timestamp"],
            "entry_timestamp": features.iloc[entry_index]["timestamp"],
            "symbol": str(current["symbol"]),
            "asset_class": asset_class,
            "regime": str(current["regime"]),
            "signal_close": float(current["adjusted_close"]),
            "entry_price": entry,
            **{column: float(current[column]) for column in FEATURE_COLUMNS},
        }
        for horizon in config.holding_periods:
            future = features.iloc[entry_index : entry_index + horizon]
            exit_price = float(future.iloc[-1]["close"])
            maximum_high = float(future["high"].max())
            minimum_low = float(future["low"].min())
            forward_return = exit_price / entry - 1.0
            net_return = forward_return - cost
            mae = minimum_low / entry - 1.0
            rows.append(
                {
                    **base,
                    "holding_period": horizon,
                    "exit_timestamp": future.iloc[-1]["timestamp"],
                    "exit_price": exit_price,
                    "forward_return": forward_return,
                    "net_forward_return": net_return,
                    "mfe": maximum_high / entry - 1.0,
                    "mae": mae,
                    "positive_return_label": int(net_return > 0.0),
                    "risk_adjusted_label": net_return - config.risk_penalty * abs(mae),
                }
            )
    return pd.DataFrame(rows)
