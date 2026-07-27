from __future__ import annotations

import csv
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from src.atlas.portfolio.core import finite_number


@dataclass(frozen=True)
class AssetMetadata:
    asset_id: str
    symbol: str
    asset_class: str
    sector: str | None
    industry: str | None
    country: str | None
    market_cap: float | None
    source: str
    status: str


class MetadataProvider(Protocol):
    def fetch(self, symbol: str) -> Mapping[str, Any]: ...


class YFinanceMetadataProvider:
    def fetch(self, symbol: str) -> Mapping[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        try:
            raw = ticker.get_info()
        except AttributeError:
            raw = ticker.info

        if not isinstance(raw, Mapping):
            return {}
        return cast(Mapping[str, Any], raw)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stock_metadata(
    asset_id: str,
    symbol: str,
    raw: Mapping[str, Any],
) -> AssetMetadata:
    sector = _clean_text(raw.get("sector"))
    industry = _clean_text(raw.get("industry"))
    country = _clean_text(raw.get("country"))
    market_cap = finite_number(raw.get("marketCap"))
    populated = sum(value is not None for value in (sector, industry, country, market_cap))
    return AssetMetadata(
        asset_id=asset_id,
        symbol=symbol,
        asset_class="stock",
        sector=sector,
        industry=industry,
        country=country,
        market_cap=market_cap,
        source="yfinance",
        status="complete" if populated == 4 else "partial" if populated else "unavailable",
    )


def _crypto_metadata(asset_id: str, symbol: str) -> AssetMetadata:
    return AssetMetadata(
        asset_id=asset_id,
        symbol=symbol,
        asset_class="crypto",
        sector="Digital Assets",
        industry="Cryptocurrency",
        country="Global",
        market_cap=None,
        source="atlas_taxonomy",
        status="complete",
    )


def read_asset_identities(path: Path) -> list[tuple[str, str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"asset_id", "symbol", "asset_class"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Asset file is missing required columns: {sorted(required)}")
        identities: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for row in reader:
            asset_id = row["asset_id"].strip()
            if not asset_id or asset_id in seen:
                continue
            identities.append((asset_id, row["symbol"].strip(), row["asset_class"].strip().lower()))
            seen.add(asset_id)
        return identities


def read_metadata(path: Path) -> dict[str, AssetMetadata]:
    if not path.exists():
        return {}
    records: dict[str, AssetMetadata] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            asset_id = row.get("asset_id", "").strip()
            if not asset_id:
                continue
            records[asset_id] = AssetMetadata(
                asset_id=asset_id,
                symbol=row.get("symbol", "").strip(),
                asset_class=row.get("asset_class", "").strip(),
                sector=_clean_text(row.get("sector")),
                industry=_clean_text(row.get("industry")),
                country=_clean_text(row.get("country")),
                market_cap=finite_number(row.get("market_cap")),
                source=row.get("source", "").strip() or "unknown",
                status=row.get("status", "").strip() or "unknown",
            )
    return records


def write_metadata(path: Path, records: Iterable[AssetMetadata]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "asset_id",
        "symbol",
        "asset_class",
        "sector",
        "industry",
        "country",
        "market_cap",
        "source",
        "status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in sorted(records, key=lambda value: value.asset_id):
            writer.writerow(
                {
                    "asset_id": item.asset_id,
                    "symbol": item.symbol,
                    "asset_class": item.asset_class,
                    "sector": item.sector or "",
                    "industry": item.industry or "",
                    "country": item.country or "",
                    "market_cap": "" if item.market_cap is None else item.market_cap,
                    "source": item.source,
                    "status": item.status,
                }
            )


def enrich_metadata(
    identities: Iterable[tuple[str, str, str]],
    existing: Mapping[str, AssetMetadata] | None = None,
    provider: MetadataProvider | None = None,
    *,
    force: bool = False,
    limit: int | None = None,
    delay_seconds: float = 0.0,
    on_progress: Callable[[int, int, AssetMetadata], None] | None = None,
) -> dict[str, AssetMetadata]:
    output = dict(existing or {})
    provider = provider or YFinanceMetadataProvider()
    items = list(identities)
    fetched = 0
    for index, (asset_id, symbol, asset_class) in enumerate(items, start=1):
        if not force and asset_id in output and output[asset_id].status in {"complete", "partial"}:
            continue
        if limit is not None and fetched >= limit:
            break
        if asset_class == "crypto":
            record = _crypto_metadata(asset_id, symbol)
        elif asset_class == "stock":
            try:
                record = _stock_metadata(asset_id, symbol, provider.fetch(symbol))
            except Exception:
                record = AssetMetadata(
                    asset_id=asset_id,
                    symbol=symbol,
                    asset_class=asset_class,
                    sector=None,
                    industry=None,
                    country=None,
                    market_cap=None,
                    source="yfinance",
                    status="error",
                )
        else:
            record = AssetMetadata(
                asset_id=asset_id,
                symbol=symbol,
                asset_class=asset_class,
                sector=None,
                industry=None,
                country=None,
                market_cap=None,
                source="atlas",
                status="unsupported",
            )
        output[asset_id] = record
        fetched += 1
        if on_progress:
            on_progress(index, len(items), record)
        if delay_seconds > 0 and asset_class == "stock":
            time.sleep(delay_seconds)
    return output
