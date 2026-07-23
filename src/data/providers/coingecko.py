from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

import pandas as pd
import requests

from src.data.schema import empty_bars, normalize_bars


class CoinGeckoProvider:
    name = "coingecko"

    def __init__(
        self,
        coin_ids: dict[str, str],
        *,
        base_url: str = "https://api.coingecko.com/api/v3",
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.coin_ids = {key.upper(): value for key, value in coin_ids.items()}
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch_daily_bars(
        self, symbol: str, asset_class: str, start: date, end: date
    ) -> pd.DataFrame:
        coin_id = self.coin_ids.get(symbol.upper())
        if coin_id is None:
            raise ValueError(f"No CoinGecko coin ID configured for {symbol}")
        if not self.api_key:
            raise RuntimeError(
                "CoinGecko requires a Demo or Pro API key for historical range downloads. "
                "Set COINGECKO_API_KEY in your local .env file, or use --provider yahoo."
            )

        start_ts = int(datetime.combine(start, time.min, tzinfo=UTC).timestamp())
        end_ts = int(datetime.combine(end, time.max, tzinfo=UTC).timestamp())
        headers: dict[str, str] = {
            "accept": "application/json",
            "x-cg-demo-api-key": self.api_key,
        }
        params: dict[str, str | int] = {
            "vs_currency": "usd",
            "from": start_ts,
            "to": end_ts,
        }
        response = requests.get(
            f"{self.base_url}/coins/{coin_id}/market_chart/range",
            params=params,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        prices = pd.DataFrame(payload.get("prices", []), columns=["timestamp_ms", "price"])
        volumes = pd.DataFrame(
            payload.get("total_volumes", []), columns=["timestamp_ms", "volume"]
        )
        if prices.empty:
            return empty_bars()

        prices["timestamp"] = pd.to_datetime(prices["timestamp_ms"], unit="ms", utc=True)
        prices["day"] = prices["timestamp"].dt.floor("D")
        daily: pd.DataFrame = prices.groupby("day").agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
        )
        if not volumes.empty:
            volumes["timestamp"] = pd.to_datetime(volumes["timestamp_ms"], unit="ms", utc=True)
            volumes["day"] = volumes["timestamp"].dt.floor("D")
            daily_volume = volumes.groupby("day")["volume"].last()
            daily = daily.join(daily_volume, how="left")
        else:
            daily["volume"] = 0.0

        daily = daily.reset_index().rename(columns={"day": "timestamp"})
        frame = daily.assign(
            symbol=symbol.upper(),
            asset_class=asset_class,
            adj_close=daily["close"],
            dividends=0.0,
            splits=0.0,
            source=self.name,
            ingested_at=datetime.now(UTC),
        )
        return normalize_bars(frame)
