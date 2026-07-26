from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.atlas.history import (
    HistoryProvider,
    history_path,
    load_history,
    merge_history,
    provider_symbol,
    update_history,
)
from src.atlas.market_models import PriceBar
from src.atlas.models import AtlasConfig
from src.atlas.universe import UniverseAsset, write_registry


class FakeProvider(HistoryProvider):
    def __init__(self, bars: list[PriceBar]) -> None:
        self.bars = bars
        self.calls: list[tuple[str, date, date]] = []

    def fetch_daily(self, symbol: str, *, start: date, end: date) -> list[PriceBar]:
        self.calls.append((symbol, start, end))
        return [bar for bar in self.bars if start <= date.fromisoformat(bar.timestamp) < end]


def _asset(
    asset_id: str,
    symbol: str,
    asset_class: str,
    market_cap: float | None = None,
) -> UniverseAsset:
    return UniverseAsset(
        asset_id=asset_id,
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


def _bar(day: int, close: float) -> PriceBar:
    return PriceBar(
        timestamp=f"2026-01-{day:02d}",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def test_provider_symbol() -> None:
    assert provider_symbol(_asset("stock:BRK.B", "BRK.B", "stock")) == "BRK-B"
    assert provider_symbol(_asset("crypto:bitcoin", "BTC", "crypto")) == "BTC-USD"


def test_merge_history_replaces_duplicate_timestamp() -> None:
    merged = merge_history([_bar(1, 10.0), _bar(2, 11.0)], [_bar(2, 12.0), _bar(3, 13.0)])
    assert [bar.close for bar in merged] == [10.0, 12.0, 13.0]


def test_update_history_writes_incremental_files(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    history_root = tmp_path / "history"
    report_path = tmp_path / "report.json"
    stock = _asset("stock:AAPL", "AAPL", "stock")
    crypto = _asset("crypto:bitcoin", "BTC", "crypto", market_cap=1_000_000.0)
    write_registry(registry_path, [stock, crypto])
    config = AtlasConfig(
        universe_registry_path=registry_path,
        market_history_root=history_root,
        history_report_path=report_path,
        history_stock_limit=1,
        history_crypto_limit=1,
        history_lookback_days=10,
    )
    provider = FakeProvider([_bar(1, 10.0), _bar(2, 11.0)])
    result = update_history(config, provider=provider, today=date(2026, 1, 3))
    assert result.complete
    assert result.selected_assets == 2
    assert result.downloaded_rows == 4
    assert len(load_history(history_path(history_root, stock))) == 2
    assert json.loads(report_path.read_text(encoding="utf-8"))["platform_version"] == "2.2.1"


def test_update_history_starts_after_latest_bar(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    history_root = tmp_path / "history"
    stock = _asset("stock:AAPL", "AAPL", "stock")
    write_registry(registry_path, [stock])
    output = history_path(history_root, stock)
    output.parent.mkdir(parents=True)
    output.write_text(
        "timestamp,open,high,low,close,volume\n2026-01-01,10,11,9,10,1000\n",
        encoding="utf-8",
    )
    config = AtlasConfig(
        universe_registry_path=registry_path,
        market_history_root=history_root,
        history_report_path=tmp_path / "report.json",
        history_stock_limit=1,
        history_crypto_limit=0,
    )
    provider = FakeProvider([_bar(2, 11.0)])
    update_history(config, provider=provider, today=date(2026, 1, 2))
    assert provider.calls[0][1] == date(2026, 1, 2)
    assert len(load_history(output)) == 2
