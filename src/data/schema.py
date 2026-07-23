from __future__ import annotations

from typing import Final

import pandas as pd

BAR_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp", "symbol", "asset_class", "open", "high", "low", "close",
    "adj_close", "volume", "dividends", "splits", "source", "ingested_at",
)
NUMERIC_COLUMNS: Final[tuple[str, ...]] = (
    "open", "high", "low", "close", "adj_close", "volume", "dividends", "splits",
)


def empty_bars() -> pd.DataFrame:
    return pd.DataFrame(columns=list(BAR_COLUMNS))


def normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    missing = [column for column in BAR_COLUMNS if column not in result.columns]
    if missing:
        raise ValueError(f"Missing normalized columns: {missing}")
    result = result.loc[:, list(BAR_COLUMNS)]
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result["ingested_at"] = pd.to_datetime(result["ingested_at"], utc=True)
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["symbol"] = result["symbol"].astype("string")
    result["asset_class"] = result["asset_class"].astype("string")
    result["source"] = result["source"].astype("string")
    return result.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
