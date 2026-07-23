from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from src.data.schema import empty_bars, normalize_bars


class YahooFinanceProvider:
    name = "yahoo"

    def __init__(self, *, auto_adjust: bool = False, repair: bool = True) -> None:
        self.auto_adjust = auto_adjust
        self.repair = repair

    def fetch_daily_bars(
        self, symbol: str, asset_class: str, start: date, end: date
    ) -> pd.DataFrame:
        # yfinance end is exclusive, so add one day to honor an inclusive CLI end date.
        raw = yf.download(
            tickers=symbol,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=self.auto_adjust,
            actions=True,
            repair=self.repair,
            progress=False,
            threads=False,
            group_by="column",
            multi_level_index=False,
        )
        if raw.empty:
            return empty_bars()
        raw = raw.reset_index()
        columns = {str(column).lower().replace(" ", "_"): column for column in raw.columns}

        def series(name: str, default: float = 0.0) -> Any:
            source = columns.get(name)
            return raw[source] if source is not None else default

        close = series("close")
        frame = pd.DataFrame(
            {
                "timestamp": series("date"),
                "symbol": symbol.upper(),
                "asset_class": asset_class,
                "open": series("open"),
                "high": series("high"),
                "low": series("low"),
                "close": close,
                "adj_close": series("adj_close", close),
                "volume": series("volume"),
                "dividends": series("dividends"),
                "splits": series("stock_splits"),
                "source": self.name,
                "ingested_at": datetime.now(UTC),
            }
        )
        return normalize_bars(frame)
