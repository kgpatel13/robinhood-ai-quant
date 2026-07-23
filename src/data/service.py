from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.providers import CoinGeckoProvider, HistoricalDataProvider, YahooFinanceProvider
from src.data.quality import DataQualityValidator, QualityReport
from src.data.storage import ParquetBarStore


class MarketDataService:
    def __init__(self, config: dict[str, Any], validated_root: Path) -> None:
        self.config = config
        storage = config["storage"]
        self.store = ParquetBarStore(validated_root, str(storage.get("compression", "snappy")))
        self.validator = DataQualityValidator(int(config["quality"].get("minimum_rows", 2)))

    def provider(self, name: str) -> HistoricalDataProvider:
        providers = self.config["providers"]
        if name == "yahoo":
            settings = providers["yahoo"]
            return YahooFinanceProvider(
                auto_adjust=bool(settings.get("auto_adjust", False)),
                repair=bool(settings.get("repair", True)),
            )
        if name == "coingecko":
            settings = providers["coingecko"]
            return CoinGeckoProvider(
                coin_ids=dict(settings["coin_ids"]),
                base_url=str(os.getenv("COINGECKO_API_BASE_URL", settings["base_url"])),
                api_key=os.getenv("COINGECKO_API_KEY"),
                timeout_seconds=int(settings.get("timeout_seconds", 30)),
            )
        raise ValueError(f"Unknown provider: {name}")

    def download(
        self, symbol: str, asset_class: str, start: date, end: date, provider_name: str
    ) -> tuple[Path, QualityReport]:
        frame = self.provider(provider_name).fetch_daily_bars(symbol, asset_class, start, end)
        report = self.validator.validate(frame)
        if not report.passed:
            raise ValueError(f"Data quality failed: {json.dumps(report.to_dict())}")
        path = self.store.write(frame, asset_class, symbol)
        return path, report

    def validate_file(self, path: Path) -> QualityReport:
        frame = pd.read_parquet(path)
        return self.validator.validate(frame)
