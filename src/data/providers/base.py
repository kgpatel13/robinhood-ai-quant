from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


class HistoricalDataProvider(Protocol):
    name: str

    def fetch_daily_bars(
        self, symbol: str, asset_class: str, start: date, end: date
    ) -> pd.DataFrame: ...
