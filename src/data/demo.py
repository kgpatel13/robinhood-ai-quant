from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.data.schema import normalize_bars


def make_demo_bars(symbol: str = "DEMO", asset_class: str = "stock", rows: int = 10) -> pd.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    records = []
    for index in range(rows):
        close = 100.0 + index
        records.append(
            {
                "timestamp": start + timedelta(days=index),
                "symbol": symbol,
                "asset_class": asset_class,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000 + index,
                "dividends": 0.0,
                "splits": 0.0,
                "source": "demo",
                "ingested_at": datetime.now(UTC),
            }
        )
    return normalize_bars(pd.DataFrame(records))
