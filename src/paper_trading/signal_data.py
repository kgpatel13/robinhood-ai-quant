from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.research_lab.data import HistoricalDataService


@dataclass(frozen=True)
class YahooSignalDataProvider:
    period: str = "6mo"
    interval: str = "1d"

    def bars(self, symbol: str) -> pd.DataFrame:
        import yfinance as yf

        frame = yf.download(
            symbol,
            period=self.period,
            interval=self.interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if frame.empty:
            raise ValueError(f"no bars returned for {symbol}")
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame.columns = [str(column).lower() for column in frame.columns]
        return HistoricalDataService.normalize(frame)


@dataclass
class StaticSignalDataProvider:
    frames: dict[str, pd.DataFrame]

    def bars(self, symbol: str) -> pd.DataFrame:
        try:
            return self.frames[symbol].copy()
        except KeyError as exc:
            raise ValueError(f"no bars configured for {symbol}") from exc
