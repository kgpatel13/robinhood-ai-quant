from __future__ import annotations

import csv
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from src.atlas.market_models import PriceBar
from src.atlas.models import AtlasConfig
from src.atlas.universe import UniverseAsset, load_registry

PLATFORM_VERSION = "2.2.1"


class HistoryProviderError(RuntimeError):
    """Raised when a historical-data provider cannot return usable bars."""


class HistoryProvider(Protocol):
    def fetch_daily(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
    ) -> list[PriceBar]: ...


@dataclass(frozen=True)
class AssetHistoryResult:
    asset_id: str
    symbol: str
    provider_symbol: str
    status: str
    existing_rows: int
    downloaded_rows: int
    final_rows: int
    first_timestamp: str | None
    last_timestamp: str | None
    output_path: str
    error: str | None = None


@dataclass(frozen=True)
class HistoryUpdateResult:
    platform_version: str
    generated_at_utc: str
    selected_assets: int
    successful_assets: int
    failed_assets: int
    skipped_assets: int
    downloaded_rows: int
    total_rows: int
    history_root: str
    report_path: str
    complete: bool
    assets: tuple[AssetHistoryResult, ...]


class YFinanceHistoryProvider:
    def fetch_daily(self, symbol: str, *, start: date, end: date) -> list[PriceBar]:
        try:
            import yfinance as yf

            frame = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # yfinance raises several third-party exception types
            raise HistoryProviderError(f"yfinance failed for {symbol}: {exc}") from exc
        if frame.empty:
            return []
        return _frame_to_bars(frame, symbol)


def _frame_to_bars(frame: pd.DataFrame, symbol: str) -> list[PriceBar]:
    normalized = frame.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = normalized.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - {str(column) for column in normalized.columns}
    if missing:
        raise HistoryProviderError(
            f"yfinance response for {symbol} is missing columns: {sorted(missing)}"
        )
    bars: list[PriceBar] = []
    for timestamp, row in normalized.iterrows():
        values = [row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]]
        if any(pd.isna(value) for value in values):
            continue
        bar = PriceBar(
            timestamp=pd.Timestamp(str(timestamp)).date().isoformat(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
        )
        if _valid_bar(bar):
            bars.append(bar)
    return sorted(bars, key=lambda item: item.timestamp)


def _valid_bar(bar: PriceBar) -> bool:
    if min(bar.open, bar.high, bar.low, bar.close) <= 0.0 or bar.volume < 0.0:
        return False
    return bar.high >= max(bar.open, bar.close, bar.low) and bar.low <= min(
        bar.open, bar.close, bar.high
    )


def provider_symbol(asset: UniverseAsset) -> str:
    if asset.asset_class == "crypto":
        return f"{asset.symbol}-USD"
    return asset.symbol.replace(".", "-")


def history_path(root: Path, asset: UniverseAsset) -> Path:
    safe_id = asset.asset_id.replace(":", "__").replace("/", "_")
    return root / f"{safe_id}.csv"


def load_history(path: Path) -> list[PriceBar]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        bars: list[PriceBar] = []
        for row in reader:
            bars.append(
                PriceBar(
                    timestamp=row["timestamp"].strip(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    return sorted((bar for bar in bars if _valid_bar(bar)), key=lambda item: item.timestamp)


def merge_history(existing: Sequence[PriceBar], incoming: Sequence[PriceBar]) -> list[PriceBar]:
    merged = {bar.timestamp: bar for bar in existing}
    for bar in incoming:
        if _valid_bar(bar):
            merged[bar.timestamp] = bar
    return sorted(merged.values(), key=lambda item: item.timestamp)


def write_history(path: Path, bars: Sequence[PriceBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
        )
        writer.writeheader()
        writer.writerows(asdict(bar) for bar in bars)
        temporary_path = Path(stream.name)
    temporary_path.replace(path)


def _select_assets(config: AtlasConfig, registry: Sequence[UniverseAsset]) -> list[UniverseAsset]:
    active = [asset for asset in registry if asset.active and asset.tradable]
    stocks = sorted(
        (asset for asset in active if asset.asset_class == "stock"),
        key=lambda item: item.symbol,
    )[: config.history_stock_limit]
    crypto = sorted(
        (asset for asset in active if asset.asset_class == "crypto"),
        key=lambda item: (-(item.market_cap or 0.0), item.symbol),
    )[: config.history_crypto_limit]
    return stocks + crypto


def _incremental_start(existing: Sequence[PriceBar], fallback: date) -> date:
    if not existing:
        return fallback
    latest = date.fromisoformat(existing[-1].timestamp[:10])
    return latest + timedelta(days=1)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        temporary_path = Path(stream.name)
    temporary_path.replace(path)


def update_history(
    config: AtlasConfig,
    *,
    provider: HistoryProvider | None = None,
    today: date | None = None,
) -> HistoryUpdateResult:
    generated_at = datetime.now(UTC).isoformat()
    current_day = today or datetime.now(UTC).date()
    end = current_day + timedelta(days=1)
    fallback_start = current_day - timedelta(days=config.history_lookback_days)
    registry = load_registry(config.universe_registry_path)
    selected = _select_assets(config, registry)
    data_provider = provider or YFinanceHistoryProvider()
    results: list[AssetHistoryResult] = []

    for asset in selected:
        output = history_path(config.market_history_root, asset)
        existing = load_history(output)
        start = _incremental_start(existing, fallback_start)
        symbol = provider_symbol(asset)
        if start >= end:
            results.append(
                AssetHistoryResult(
                    asset_id=asset.asset_id,
                    symbol=asset.symbol,
                    provider_symbol=symbol,
                    status="current",
                    existing_rows=len(existing),
                    downloaded_rows=0,
                    final_rows=len(existing),
                    first_timestamp=existing[0].timestamp if existing else None,
                    last_timestamp=existing[-1].timestamp if existing else None,
                    output_path=str(output),
                )
            )
            continue
        try:
            downloaded = data_provider.fetch_daily(symbol, start=start, end=end)
            merged = merge_history(existing, downloaded)
            if merged:
                write_history(output, merged)
            status = "updated" if downloaded else ("current" if existing else "no_data")
            results.append(
                AssetHistoryResult(
                    asset_id=asset.asset_id,
                    symbol=asset.symbol,
                    provider_symbol=symbol,
                    status=status,
                    existing_rows=len(existing),
                    downloaded_rows=len(downloaded),
                    final_rows=len(merged),
                    first_timestamp=merged[0].timestamp if merged else None,
                    last_timestamp=merged[-1].timestamp if merged else None,
                    output_path=str(output),
                )
            )
        except (HistoryProviderError, ValueError, OSError) as exc:
            results.append(
                AssetHistoryResult(
                    asset_id=asset.asset_id,
                    symbol=asset.symbol,
                    provider_symbol=symbol,
                    status="failed",
                    existing_rows=len(existing),
                    downloaded_rows=0,
                    final_rows=len(existing),
                    first_timestamp=existing[0].timestamp if existing else None,
                    last_timestamp=existing[-1].timestamp if existing else None,
                    output_path=str(output),
                    error=str(exc),
                )
            )

    failed = sum(item.status == "failed" for item in results)
    skipped = sum(item.status in {"current", "no_data"} for item in results)
    result = HistoryUpdateResult(
        platform_version=PLATFORM_VERSION,
        generated_at_utc=generated_at,
        selected_assets=len(selected),
        successful_assets=len(results) - failed,
        failed_assets=failed,
        skipped_assets=skipped,
        downloaded_rows=sum(item.downloaded_rows for item in results),
        total_rows=sum(item.final_rows for item in results),
        history_root=str(config.market_history_root),
        report_path=str(config.history_report_path),
        complete=failed == 0,
        assets=tuple(results),
    )
    _atomic_write_json(config.history_report_path, asdict(result))
    return result
