from datetime import date
from unittest.mock import patch

import pandas as pd

from src.data.providers.yahoo import YahooFinanceProvider


def test_yahoo_normalizes_download() -> None:
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "Open": [100.0, 101.0], "High": [102.0, 103.0], "Low": [99.0, 100.0],
            "Close": [101.0, 102.0], "Adj Close": [100.5, 101.5], "Volume": [10, 20],
            "Dividends": [0.0, 0.1], "Stock Splits": [0.0, 0.0],
        }
    ).set_index("Date")
    with patch("src.data.providers.yahoo.yf.download", return_value=raw):
        frame = YahooFinanceProvider().fetch_daily_bars(
            "SPY", "stock", date(2025, 1, 1), date(2025, 1, 3)
        )
    assert len(frame) == 2
    assert frame.iloc[0]["symbol"] == "SPY"
    assert frame.iloc[1]["dividends"] == 0.1
