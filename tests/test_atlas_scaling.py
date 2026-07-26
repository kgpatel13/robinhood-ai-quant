from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from src.atlas.history import HistoryProvider, update_history
from src.atlas.market import run_market_intelligence
from src.atlas.market_models import PriceBar
from src.atlas.models import AtlasConfig
from src.atlas.scaling import inspect_history_inventory, select_universe_batch
from src.atlas.universe import UniverseAsset, write_registry


class FakeProvider(HistoryProvider):
    def fetch_daily(self, symbol: str, *, start: object, end: object) -> list[PriceBar]:
        return _bars(80)


def _asset(
    symbol: str, asset_class: str = "stock", market_cap: float | None = None
) -> UniverseAsset:
    return UniverseAsset(
        asset_id=f"{asset_class}:{symbol.lower()}",
        symbol=symbol,
        name=symbol,
        asset_class=asset_class,  # type: ignore[arg-type]
        exchange="TEST",
        source="test",
        source_id=symbol.lower(),
        active=True,
        tradable=True,
        is_etf=False,
        market_cap=market_cap,
    )


def _bars(count: int) -> list[PriceBar]:
    return [
        PriceBar(
            timestamp=f"2025-{1 + index // 28:02d}-{1 + index % 28:02d}",
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1_000_000.0,
        )
        for index in range(count)
    ]


def _write_bars(path: Path, bars: list[PriceBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(PriceBar.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(bar) for bar in bars)


def test_select_universe_batch_is_deterministic() -> None:
    registry = [
        _asset("BBB"),
        _asset("AAA"),
        _asset("LOW", "crypto", 10.0),
        _asset("HIGH", "crypto", 100.0),
    ]
    batch = select_universe_batch(
        registry,
        stock_limit=None,
        crypto_limit=None,
        offset=1,
        batch_size=2,
    )
    assert [asset.symbol for asset in batch.assets] == ["BBB", "HIGH"]
    assert batch.eligible_assets == 4


def test_inventory_and_parallel_market_pipeline(tmp_path: Path) -> None:
    registry = [_asset("AAA"), _asset("BBB")]
    registry_path = tmp_path / "registry.json"
    history_root = tmp_path / "daily"
    write_registry(registry_path, registry)
    _write_bars(history_root / "stock__aaa.csv", _bars(80))
    config = AtlasConfig(
        universe_registry_path=registry_path,
        market_history_root=history_root,
        market_feature_store_path=tmp_path / "features.csv",
        feature_intelligence_store_path=tmp_path / "features_v2.csv",
        feature_dictionary_path=tmp_path / "dictionary.json",
        feature_statistics_path=tmp_path / "statistics.json",
        market_snapshot_path=tmp_path / "snapshot.json",
        market_report_path=tmp_path / "report.json",
    )
    inventory = inspect_history_inventory(registry, history_root, minimum_bars=60)
    assert inventory.assets_with_history == 1
    assert inventory.assets_ready_for_features == 1
    result = run_market_intelligence(config, max_workers=2)
    assert result.processed_assets == 1


def test_parallel_history_batch_respects_batch_size(tmp_path: Path) -> None:
    registry = [_asset("AAA"), _asset("BBB"), _asset("CCC")]
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path, registry)
    config = AtlasConfig(
        universe_registry_path=registry_path,
        market_history_root=tmp_path / "daily",
        history_report_path=tmp_path / "history_report.json",
        history_stock_limit=3,
        history_crypto_limit=0,
    )
    result = update_history(
        config,
        provider=FakeProvider(),
        batch_size=2,
        workers=2,
    )
    assert result.selected_assets == 2
    assert result.successful_assets == 2
