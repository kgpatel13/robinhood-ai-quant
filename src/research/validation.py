from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
}


@dataclass(frozen=True)
class DatasetValidation:
    path: Path
    symbol: str
    rows: int
    start: pd.Timestamp
    end: pd.Timestamp


def validate_dataset(frame: pd.DataFrame, path: Path = Path("<memory>")) -> DatasetValidation:
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    extra = set(frame.columns).difference(REQUIRED_COLUMNS)
    if missing or extra:
        raise ValueError(
            f"Invalid schema for {path}: missing={sorted(missing)} extra={sorted(extra)}"
        )
    if frame.empty:
        raise ValueError(f"Dataset is empty: {path}")
    symbols = frame["symbol"].astype(str).unique().tolist()
    if len(symbols) != 1:
        raise ValueError(f"Dataset must contain exactly one symbol: {path}")
    if frame["timestamp"].duplicated().any():
        raise ValueError(f"Duplicate timestamps detected: {path}")
    if frame["timestamp"].isna().any() or frame.isna().any().any():
        raise ValueError(f"Missing values detected: {path}")
    ordered = frame.sort_values("timestamp")
    if not ordered["timestamp"].is_monotonic_increasing:
        raise ValueError(f"Timestamps are not monotonic: {path}")
    invalid_ohlc = (
        (ordered["high"] < ordered[["open", "close", "low"]].max(axis=1))
        | (ordered["low"] > ordered[["open", "close", "high"]].min(axis=1))
        | (ordered[["open", "high", "low", "close", "adjusted_close"]] <= 0).any(axis=1)
        | (ordered["volume"] < 0)
    )
    if invalid_ohlc.any():
        raise ValueError(f"Invalid OHLCV rows detected: {path}")
    return DatasetValidation(
        path=path,
        symbol=symbols[0],
        rows=len(ordered),
        start=pd.Timestamp(ordered["timestamp"].iloc[0]),
        end=pd.Timestamp(ordered["timestamp"].iloc[-1]),
    )


def discover_datasets(root: Path) -> dict[str, Path]:
    registry: dict[str, Path] = {}
    for path in sorted(root.rglob("*.parquet")):
        frame = pd.read_parquet(path)
        result = validate_dataset(frame, path)
        if result.symbol in registry:
            raise ValueError(
                f"Duplicate symbol {result.symbol}: {registry[result.symbol]} and {path}"
            )
        registry[result.symbol] = path
    if not registry:
        raise ValueError(f"No parquet datasets found under {root}")
    return registry
