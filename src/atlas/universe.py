from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import requests
from dotenv import load_dotenv

from src.atlas.models import AssetClass, AtlasConfig

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


class UniverseDownloadError(RuntimeError):
    """Raised when a universe provider cannot return a valid complete response."""


class HttpTransport(Protocol):
    def get_text(self, url: str, *, timeout_seconds: float) -> str: ...

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Any: ...


class RequestsTransport:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", "AtlasAI/2.1 universe-intelligence")

    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        try:
            response = self._session.get(url, timeout=timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UniverseDownloadError(f"Unable to download {url}: {exc}") from exc
        return response.text

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Any:
        try:
            response = self._session.get(
                url,
                params=dict(params),
                headers=dict(headers),
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise UniverseDownloadError(f"Unable to download {url}: {exc}") from exc


@dataclass(frozen=True)
class UniverseAsset:
    asset_id: str
    symbol: str
    name: str
    asset_class: AssetClass
    exchange: str
    source: str
    source_id: str
    active: bool
    tradable: bool
    is_etf: bool
    market_cap: float | None = None
    price: float | None = None
    volume_24h: float | None = None
    first_seen_utc: str = ""
    last_seen_utc: str = ""


@dataclass(frozen=True)
class UniverseUpdateResult:
    platform_version: str
    updated_at_utc: str
    registry_path: str
    total_assets: int
    active_assets: int
    tradable_assets: int
    stock_assets: int
    crypto_assets: int
    added_assets: int
    updated_assets: int
    deactivated_assets: int
    provider_counts: dict[str, int]
    provider_errors: dict[str, str]
    complete: bool


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_symbol(value: str) -> str:
    return value.strip().upper().replace(" ", "-")


def _parse_pipe_table(text: str) -> list[dict[str, str]]:
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.startswith("File Creation Time")
    ]
    if not lines:
        raise UniverseDownloadError("Symbol directory response was empty")
    reader = csv.DictReader(lines, delimiter="|")
    rows = []
    for row in reader:
        cleaned = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def _is_test_issue(row: Mapping[str, str]) -> bool:
    return row.get("Test Issue", "N").upper() == "Y"


def _is_etf(row: Mapping[str, str]) -> bool:
    return row.get("ETF", "N").upper() == "Y"


def _security_is_tradable(name: str, *, is_etf: bool) -> bool:
    blocked_tokens = (
        "WARRANT",
        "RIGHT",
        "UNIT",
        "PREFERRED",
        "PFD",
        "DEPOSITARY SHARES",
        "TEST STOCK",
    )
    upper_name = name.upper()
    return not is_etf and not any(token in upper_name for token in blocked_tokens)


class NasdaqSymbolDirectoryProvider:
    source = "nasdaq_symbol_directory"

    def __init__(
        self,
        transport: HttpTransport,
        *,
        nasdaq_url: str = NASDAQ_LISTED_URL,
        other_url: str = OTHER_LISTED_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._transport = transport
        self._nasdaq_url = nasdaq_url
        self._other_url = other_url
        self._timeout_seconds = timeout_seconds

    def fetch(self, observed_at_utc: str) -> list[UniverseAsset]:
        assets: list[UniverseAsset] = []
        assets.extend(
            self._parse_nasdaq(
                self._transport.get_text(self._nasdaq_url, timeout_seconds=self._timeout_seconds),
                observed_at_utc,
            )
        )
        assets.extend(
            self._parse_other(
                self._transport.get_text(self._other_url, timeout_seconds=self._timeout_seconds),
                observed_at_utc,
            )
        )
        if not assets:
            raise UniverseDownloadError("Nasdaq symbol directory returned no eligible securities")
        deduplicated = {asset.asset_id: asset for asset in assets}
        return sorted(deduplicated.values(), key=lambda item: item.asset_id)

    def _parse_nasdaq(self, text: str, observed_at_utc: str) -> list[UniverseAsset]:
        assets: list[UniverseAsset] = []
        for row in _parse_pipe_table(text):
            if _is_test_issue(row):
                continue
            symbol = _normalize_symbol(row.get("Symbol", ""))
            name = row.get("Security Name", "").strip()
            if not symbol or not name:
                continue
            etf = _is_etf(row)
            assets.append(
                UniverseAsset(
                    asset_id=f"stock:{symbol}",
                    symbol=symbol,
                    name=name,
                    asset_class="stock",
                    exchange="NASDAQ",
                    source=self.source,
                    source_id=symbol,
                    active=True,
                    tradable=_security_is_tradable(name, is_etf=etf),
                    is_etf=etf,
                    first_seen_utc=observed_at_utc,
                    last_seen_utc=observed_at_utc,
                )
            )
        return assets

    def _parse_other(self, text: str, observed_at_utc: str) -> list[UniverseAsset]:
        exchange_names = {
            "A": "NYSE American",
            "N": "NYSE",
            "P": "NYSE Arca",
            "Z": "Cboe BZX",
            "V": "IEX",
        }
        assets: list[UniverseAsset] = []
        for row in _parse_pipe_table(text):
            if _is_test_issue(row):
                continue
            symbol = _normalize_symbol(row.get("NASDAQ Symbol") or row.get("ACT Symbol", ""))
            name = row.get("Security Name", "").strip()
            if not symbol or not name:
                continue
            etf = _is_etf(row)
            exchange_code = row.get("Exchange", "").upper()
            assets.append(
                UniverseAsset(
                    asset_id=f"stock:{symbol}",
                    symbol=symbol,
                    name=name,
                    asset_class="stock",
                    exchange=exchange_names.get(exchange_code, exchange_code or "OTHER"),
                    source=self.source,
                    source_id=symbol,
                    active=True,
                    tradable=_security_is_tradable(name, is_etf=etf),
                    is_etf=etf,
                    first_seen_utc=observed_at_utc,
                    last_seen_utc=observed_at_utc,
                )
            )
        return assets


class CoinGeckoMarketsProvider:
    source = "coingecko"

    def __init__(
        self,
        transport: HttpTransport,
        *,
        api_key: str,
        markets_url: str = COINGECKO_MARKETS_URL,
        maximum_assets: int = 250,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("CoinGecko demo API key is required")
        self._transport = transport
        self._api_key = api_key.strip()
        self._markets_url = markets_url
        self._maximum_assets = maximum_assets
        self._timeout_seconds = timeout_seconds

    def fetch(self, observed_at_utc: str) -> list[UniverseAsset]:
        assets: list[UniverseAsset] = []
        page = 1
        page_size = min(250, self._maximum_assets)
        while len(assets) < self._maximum_assets:
            payload = self._transport.get_json(
                self._markets_url,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": page_size,
                    "page": page,
                    "sparkline": "false",
                },
                headers={"x-cg-demo-api-key": self._api_key},
                timeout_seconds=self._timeout_seconds,
            )
            if not isinstance(payload, list):
                raise UniverseDownloadError("CoinGecko markets response was not a list")
            if not payload:
                break
            for raw in payload:
                if not isinstance(raw, Mapping):
                    continue
                source_id = str(raw.get("id", "")).strip()
                symbol = _normalize_symbol(str(raw.get("symbol", "")))
                name = str(raw.get("name", "")).strip()
                if not source_id or not symbol or not name:
                    continue
                assets.append(
                    UniverseAsset(
                        asset_id=f"crypto:{source_id}",
                        symbol=symbol,
                        name=name,
                        asset_class="crypto",
                        exchange="AGGREGATED",
                        source=self.source,
                        source_id=source_id,
                        active=True,
                        tradable=True,
                        is_etf=False,
                        market_cap=_optional_float(raw.get("market_cap")),
                        price=_optional_float(raw.get("current_price")),
                        volume_24h=_optional_float(raw.get("total_volume")),
                        first_seen_utc=observed_at_utc,
                        last_seen_utc=observed_at_utc,
                    )
                )
                if len(assets) >= self._maximum_assets:
                    break
            if len(payload) < page_size:
                break
            page += 1
        if not assets:
            raise UniverseDownloadError("CoinGecko returned no eligible crypto assets")
        return sorted(assets, key=lambda item: item.asset_id)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_registry(path: Path) -> list[UniverseAsset]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Universe registry must contain a JSON list: {path}")
    return [UniverseAsset(**item) for item in raw]


def merge_registry(
    existing: Sequence[UniverseAsset],
    incoming_by_source: Mapping[str, Sequence[UniverseAsset]],
    successful_sources: set[str],
    observed_at_utc: str,
) -> tuple[list[UniverseAsset], int, int, int]:
    merged = {asset.asset_id: asset for asset in existing}
    added = 0
    updated = 0
    deactivated = 0

    incoming_ids_by_source = {
        source: {asset.asset_id for asset in assets}
        for source, assets in incoming_by_source.items()
    }

    for source in successful_sources:
        visible_ids = incoming_ids_by_source.get(source, set())
        for asset_id, previous_asset in list(merged.items()):
            if (
                previous_asset.source == source
                and previous_asset.active
                and asset_id not in visible_ids
            ):
                merged[asset_id] = UniverseAsset(
                    **{
                        **asdict(previous_asset),
                        "active": False,
                        "last_seen_utc": previous_asset.last_seen_utc,
                    }
                )
                deactivated += 1

    for assets in incoming_by_source.values():
        for incoming in assets:
            previous = merged.get(incoming.asset_id)
            if previous is None:
                merged[incoming.asset_id] = incoming
                added += 1
                continue
            first_seen = previous.first_seen_utc or observed_at_utc
            candidate = UniverseAsset(
                **{
                    **asdict(incoming),
                    "first_seen_utc": first_seen,
                    "last_seen_utc": observed_at_utc,
                }
            )
            if candidate != previous:
                updated += 1
            merged[incoming.asset_id] = candidate

    return sorted(merged.values(), key=lambda item: item.asset_id), added, updated, deactivated


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_registry(path: Path, assets: Sequence[UniverseAsset]) -> None:
    payload = json.dumps([asdict(asset) for asset in assets], indent=2, sort_keys=True)
    _atomic_write_text(path, payload)


def write_registry_csv(path: Path, assets: Sequence[UniverseAsset]) -> None:
    fieldnames = list(UniverseAsset.__dataclass_fields__)
    rows = [asdict(asset) for asset in assets]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def update_universe(
    config: AtlasConfig,
    *,
    include_stocks: bool = True,
    include_crypto: bool = True,
    transport: HttpTransport | None = None,
    environment: Mapping[str, str] | None = None,
) -> UniverseUpdateResult:
    observed_at_utc = _utc_now()
    http = transport or RequestsTransport()

    # Tests and callers may provide an explicit environment mapping. In normal
    # command-line use, load the project-root .env file before reading keys.
    if environment is None:
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env", override=False)
        env: Mapping[str, str] = os.environ
    else:
        env = environment

    existing = load_registry(config.universe_registry_path)
    incoming: dict[str, list[UniverseAsset]] = {}
    errors: dict[str, str] = {}
    successful_sources: set[str] = set()

    if include_stocks:
        stock_provider = NasdaqSymbolDirectoryProvider(
            http,
            nasdaq_url=config.nasdaq_listed_url,
            other_url=config.other_listed_url,
            timeout_seconds=config.universe_request_timeout_seconds,
        )
        try:
            incoming[stock_provider.source] = stock_provider.fetch(observed_at_utc)
            successful_sources.add(stock_provider.source)
        except (UniverseDownloadError, ValueError) as exc:
            errors[stock_provider.source] = str(exc)

    if include_crypto:
        configured_key_name = config.coingecko_api_key_env.strip()
        api_key = (
            (env.get(configured_key_name, "") if configured_key_name else "").strip()
            or env.get("COINGECKO_DEMO_API_KEY", "").strip()
            or env.get("COINGECKO_API_KEY", "").strip()
        )
        try:
            crypto_provider = CoinGeckoMarketsProvider(
                http,
                api_key=api_key,
                markets_url=config.coingecko_markets_url,
                maximum_assets=config.maximum_crypto_universe_assets,
                timeout_seconds=config.universe_request_timeout_seconds,
            )
            incoming[crypto_provider.source] = crypto_provider.fetch(observed_at_utc)
            successful_sources.add(crypto_provider.source)
        except (UniverseDownloadError, ValueError) as exc:
            errors[CoinGeckoMarketsProvider.source] = str(exc)

    if not successful_sources:
        raise UniverseDownloadError(
            "No universe provider completed successfully: "
            + "; ".join(f"{source}: {message}" for source, message in errors.items())
        )

    merged, added, updated, deactivated = merge_registry(
        existing,
        incoming,
        successful_sources,
        observed_at_utc,
    )
    write_registry(config.universe_registry_path, merged)
    write_registry_csv(config.universe_registry_csv_path, merged)

    active = [asset for asset in merged if asset.active]
    result = UniverseUpdateResult(
        platform_version="2.1.0",
        updated_at_utc=observed_at_utc,
        registry_path=str(config.universe_registry_path),
        total_assets=len(merged),
        active_assets=len(active),
        tradable_assets=sum(asset.tradable for asset in active),
        stock_assets=sum(asset.asset_class == "stock" for asset in active),
        crypto_assets=sum(asset.asset_class == "crypto" for asset in active),
        added_assets=added,
        updated_assets=updated,
        deactivated_assets=deactivated,
        provider_counts={source: len(assets) for source, assets in incoming.items()},
        provider_errors=errors,
        complete=not errors,
    )
    _atomic_write_text(
        config.universe_report_path,
        json.dumps(asdict(result), indent=2, sort_keys=True),
    )
    return result


def active_tradable_assets(assets: Iterable[UniverseAsset]) -> list[UniverseAsset]:
    return sorted(
        (asset for asset in assets if asset.active and asset.tradable),
        key=lambda item: (item.asset_class, item.symbol, item.source_id),
    )
