from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.atlas.models import AtlasConfig
from src.atlas.universe import (
    CoinGeckoMarketsProvider,
    NasdaqSymbolDirectoryProvider,
    UniverseAsset,
    active_tradable_assets,
    load_registry,
    merge_registry,
    update_universe,
)


class FakeTransport:
    def __init__(self) -> None:
        self.text_by_url: dict[str, str] = {}
        self.json_pages: dict[int, Any] = {}

    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        del timeout_seconds
        return self.text_by_url[url]

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Any:
        del url, headers, timeout_seconds
        return self.json_pages.get(int(params["page"]), [])


def test_nasdaq_provider_filters_test_issues_and_marks_etfs_not_tradable() -> None:
    transport = FakeTransport()
    transport.text_by_url["nasdaq"] = "\n".join(
        [
            (
                "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
                "Round Lot Size|ETF|NextShares"
            ),
            "AAA|Alpha Corp Common Stock|Q|N|N|100|N|N",
            "ETF1|Index Fund|G|N|N|100|Y|N",
            "TEST|Test Stock|Q|Y|N|100|N|N",
            "File Creation Time: 0726202621:30|||||||",
        ]
    )
    transport.text_by_url["other"] = "\n".join(
        [
            (
                "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
                "Test Issue|NASDAQ Symbol"
            ),
            "BBB|Beta Inc Common Stock|N|BBB|N|100|N|BBB",
            "File Creation Time: 0726202621:30|||||||",
        ]
    )

    provider = NasdaqSymbolDirectoryProvider(
        transport,
        nasdaq_url="nasdaq",
        other_url="other",
    )
    assets = provider.fetch("2026-07-26T00:00:00+00:00")

    assert [asset.symbol for asset in assets] == ["AAA", "BBB", "ETF1"]
    assert {asset.symbol: asset.tradable for asset in assets} == {
        "AAA": True,
        "BBB": True,
        "ETF1": False,
    }
    assert {asset.symbol: asset.exchange for asset in assets}["BBB"] == "NYSE"


def test_coingecko_provider_paginates_and_uses_source_id_for_identity() -> None:
    transport = FakeTransport()
    transport.json_pages[1] = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_cap": 1_000_000,
            "current_price": 50_000,
            "total_volume": 100_000,
        },
        {
            "id": "wrapped-bitcoin",
            "symbol": "btc",
            "name": "Wrapped Bitcoin",
            "market_cap": 500_000,
            "current_price": 50_010,
            "total_volume": 50_000,
        },
    ]
    provider = CoinGeckoMarketsProvider(
        transport,
        api_key="demo-key",
        markets_url="markets",
        maximum_assets=2,
    )

    assets = provider.fetch("2026-07-26T00:00:00+00:00")

    assert [asset.asset_id for asset in assets] == [
        "crypto:bitcoin",
        "crypto:wrapped-bitcoin",
    ]
    assert all(asset.symbol == "BTC" for asset in assets)


def test_merge_registry_deactivates_only_successful_provider_assets() -> None:
    old = [
        UniverseAsset(
            asset_id="stock:OLD",
            symbol="OLD",
            name="Old Corp",
            asset_class="stock",
            exchange="NASDAQ",
            source="nasdaq_symbol_directory",
            source_id="OLD",
            active=True,
            tradable=True,
            is_etf=False,
            first_seen_utc="first",
            last_seen_utc="last",
        ),
        UniverseAsset(
            asset_id="crypto:bitcoin",
            symbol="BTC",
            name="Bitcoin",
            asset_class="crypto",
            exchange="AGGREGATED",
            source="coingecko",
            source_id="bitcoin",
            active=True,
            tradable=True,
            is_etf=False,
            first_seen_utc="first",
            last_seen_utc="last",
        ),
    ]
    new_stock = UniverseAsset(
        asset_id="stock:NEW",
        symbol="NEW",
        name="New Corp",
        asset_class="stock",
        exchange="NASDAQ",
        source="nasdaq_symbol_directory",
        source_id="NEW",
        active=True,
        tradable=True,
        is_etf=False,
        first_seen_utc="now",
        last_seen_utc="now",
    )

    merged, added, _, deactivated = merge_registry(
        old,
        {"nasdaq_symbol_directory": [new_stock]},
        {"nasdaq_symbol_directory"},
        "now",
    )

    by_id = {asset.asset_id: asset for asset in merged}
    assert added == 1
    assert deactivated == 1
    assert not by_id["stock:OLD"].active
    assert by_id["crypto:bitcoin"].active


def test_update_universe_writes_incremental_registry_and_report(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.text_by_url["nasdaq"] = "\n".join(
        [
            (
                "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
                "Round Lot Size|ETF|NextShares"
            ),
            "AAA|Alpha Corp Common Stock|Q|N|N|100|N|N",
        ]
    )
    transport.text_by_url["other"] = "\n".join(
        [
            (
                "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
                "Test Issue|NASDAQ Symbol"
            ),
            "BBB|Beta Inc Common Stock|N|BBB|N|100|N|BBB",
        ]
    )
    transport.json_pages[1] = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_cap": 1_000_000,
            "current_price": 50_000,
            "total_volume": 100_000,
        }
    ]
    config = AtlasConfig(
        universe_registry_path=tmp_path / "registry.json",
        universe_registry_csv_path=tmp_path / "registry.csv",
        universe_report_path=tmp_path / "report.json",
        nasdaq_listed_url="nasdaq",
        other_listed_url="other",
        coingecko_markets_url="markets",
        maximum_crypto_universe_assets=1,
    )

    first = update_universe(
        config,
        transport=transport,
        environment={"COINGECKO_DEMO_API_KEY": "demo-key"},
    )
    second = update_universe(
        config,
        transport=transport,
        environment={"COINGECKO_DEMO_API_KEY": "demo-key"},
    )

    assert first.total_assets == 3
    assert first.added_assets == 3
    assert first.complete
    assert second.added_assets == 0
    assert config.universe_registry_csv_path.exists()
    assert len(load_registry(config.universe_registry_path)) == 3
    report = json.loads(config.universe_report_path.read_text(encoding="utf-8"))
    assert report["platform_version"] == "2.1.0"
    assert len(active_tradable_assets(load_registry(config.universe_registry_path))) == 3
