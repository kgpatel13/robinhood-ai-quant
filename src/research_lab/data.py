from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class HistoricalDataRequest:
    symbol: str
    start: date
    end: date
    interval: str = "1d"


class HistoricalDataService:
    """Load normalized OHLCV data from CSV or Yahoo Finance for research only."""

    @staticmethod
    def from_csv(path: str | Path) -> pd.DataFrame:
        frame = pd.read_csv(path)
        date_column = next(
            (name for name in ("date", "datetime", "timestamp") if name in frame.columns), None
        )
        if date_column is None:
            raise ValueError("CSV requires date, datetime, or timestamp column")
        frame[date_column] = pd.to_datetime(frame[date_column], utc=True)
        frame = frame.set_index(date_column)
        frame.columns = [str(column).lower() for column in frame.columns]
        return HistoricalDataService.normalize(frame)

    @staticmethod
    def from_yahoo(request: HistoricalDataRequest) -> pd.DataFrame:
        import yfinance as yf

        downloaded = yf.download(
            request.symbol,
            start=request.start.isoformat(),
            end=request.end.isoformat(),
            interval=request.interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if downloaded.empty:
            raise ValueError(f"No historical data returned for {request.symbol}")
        if isinstance(downloaded.columns, pd.MultiIndex):
            downloaded.columns = downloaded.columns.get_level_values(0)
        downloaded.columns = [str(column).lower() for column in downloaded.columns]
        return HistoricalDataService.normalize(downloaded)

    @staticmethod
    def normalize(frame: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"Historical data missing columns: {', '.join(missing)}")
        result = frame.loc[:, list(_REQUIRED_COLUMNS)].copy()
        result.index = pd.DatetimeIndex(pd.to_datetime(result.index, utc=True))
        result = result[~result.index.duplicated(keep="last")].sort_index()
        for column in _REQUIRED_COLUMNS:
            result[column] = pd.to_numeric(result[column], errors="coerce")
        result = result.dropna()
        if result.empty:
            raise ValueError("Historical data is empty after normalization")
        return result
