from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class IntradayBarConfig:
    interval_minutes: int = 5
    timezone: str = "America/New_York"
    minimum_bars: int = 20

    def __post_init__(self) -> None:
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")
        if self.minimum_bars < 2:
            raise ValueError("minimum_bars must be at least two")


@dataclass(frozen=True)
class IntradayQualityReport:
    valid: bool
    row_count: int
    duplicate_timestamps: int
    missing_intervals: int
    invalid_price_rows: int
    negative_volume_rows: int


def normalize_intraday_bars(frame: pd.DataFrame, config: IntradayBarConfig) -> pd.DataFrame:
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing intraday columns: {','.join(missing)}")
    result = frame.copy()
    if not isinstance(result.index, pd.DatetimeIndex):
        if "timestamp" not in result.columns:
            raise ValueError("intraday bars require a DatetimeIndex or timestamp column")
        result.index = pd.to_datetime(result.pop("timestamp"), utc=True)
    elif result.index.tz is None:
        result.index = result.index.tz_localize("UTC")
    datetime_index = pd.DatetimeIndex(result.index)
    result.index = datetime_index.tz_convert(config.timezone)
    result = result.sort_index()
    for column in _REQUIRED_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.loc[:, list(_REQUIRED_COLUMNS)]


def validate_intraday_bars(frame: pd.DataFrame, config: IntradayBarConfig) -> IntradayQualityReport:
    bars = normalize_intraday_bars(frame, config)
    duplicates = int(bars.index.duplicated().sum())
    price_invalid = (
        bars[["open", "high", "low", "close"]].isna().any(axis=1)
        | (bars[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (bars["high"] < bars[["open", "close", "low"]].max(axis=1))
        | (bars["low"] > bars[["open", "close", "high"]].min(axis=1))
    )
    negative_volume = bars["volume"].isna() | (bars["volume"] < 0)
    missing_intervals = 0
    if len(bars.index) > 1:
        expected = timedelta(minutes=config.interval_minutes)
        differences = bars.index.to_series().diff().dropna()
        missing_intervals = int(sum(max(0, round(delta / expected) - 1) for delta in differences))
    valid = (
        len(bars) >= config.minimum_bars
        and duplicates == 0
        and not bool(price_invalid.any())
        and not bool(negative_volume.any())
    )
    return IntradayQualityReport(
        valid=valid,
        row_count=len(bars),
        duplicate_timestamps=duplicates,
        missing_intervals=missing_intervals,
        invalid_price_rows=int(price_invalid.sum()),
        negative_volume_rows=int(negative_volume.sum()),
    )
