from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from src.atlas.intelligence import score_opportunity
from src.atlas.models import AssetClass, AtlasConfig, AtlasRunResult, MarketSnapshot
from src.atlas.research import create_manifest, file_sha256

PLATFORM_VERSION = "2.1.0"
_REQUIRED_COLUMNS = {
    "symbol",
    "price",
    "average_daily_volume",
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "distance_from_20d_high",
    "relative_volume",
    "spread_bps",
}


def load_config(path: Path) -> AtlasConfig:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = AtlasConfig()

    return AtlasConfig(
        output_root=Path(raw.get("output_root", defaults.output_root)),
        experiment_root=Path(raw.get("experiment_root", defaults.experiment_root)),
        baseline_signoff=Path(raw.get("baseline_signoff", defaults.baseline_signoff)),
        stock_universe_path=Path(raw.get("stock_universe_path", defaults.stock_universe_path)),
        crypto_universe_path=Path(raw.get("crypto_universe_path", defaults.crypto_universe_path)),
        universe_registry_path=Path(
            raw.get("universe_registry_path", defaults.universe_registry_path)
        ),
        universe_registry_csv_path=Path(
            raw.get("universe_registry_csv_path", defaults.universe_registry_csv_path)
        ),
        universe_report_path=Path(raw.get("universe_report_path", defaults.universe_report_path)),
        nasdaq_listed_url=str(raw.get("nasdaq_listed_url", defaults.nasdaq_listed_url)),
        other_listed_url=str(raw.get("other_listed_url", defaults.other_listed_url)),
        coingecko_markets_url=str(raw.get("coingecko_markets_url", defaults.coingecko_markets_url)),
        coingecko_api_key_env=str(raw.get("coingecko_api_key_env", defaults.coingecko_api_key_env)),
        maximum_crypto_universe_assets=int(
            raw.get(
                "maximum_crypto_universe_assets",
                defaults.maximum_crypto_universe_assets,
            )
        ),
        universe_request_timeout_seconds=float(
            raw.get(
                "universe_request_timeout_seconds",
                defaults.universe_request_timeout_seconds,
            )
        ),
        random_seed=int(raw.get("random_seed", defaults.random_seed)),
        top_candidates=int(raw.get("top_candidates", defaults.top_candidates)),
        minimum_price=float(raw.get("minimum_price", defaults.minimum_price)),
        minimum_daily_dollar_volume=float(
            raw.get(
                "minimum_daily_dollar_volume",
                defaults.minimum_daily_dollar_volume,
            )
        ),
        maximum_stock_holding_days=int(
            raw.get(
                "maximum_stock_holding_days",
                defaults.maximum_stock_holding_days,
            )
        ),
        maximum_crypto_holding_days=int(
            raw.get(
                "maximum_crypto_holding_days",
                defaults.maximum_crypto_holding_days,
            )
        ),
        paper_trading_enabled=bool(
            raw.get(
                "paper_trading_enabled",
                defaults.paper_trading_enabled,
            )
        ),
        live_trading_enabled=bool(
            raw.get(
                "live_trading_enabled",
                defaults.live_trading_enabled,
            )
        ),
    )


def _read_universe(path: Path, asset_class: AssetClass) -> list[MarketSnapshot]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or [])
        missing = _REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
        snapshots: list[MarketSnapshot] = []
        for row in reader:
            snapshots.append(
                MarketSnapshot(
                    symbol=row["symbol"].strip().upper(),
                    asset_class=asset_class,
                    price=float(row["price"]),
                    average_daily_volume=float(row["average_daily_volume"]),
                    return_1d=float(row["return_1d"]),
                    return_5d=float(row["return_5d"]),
                    return_20d=float(row["return_20d"]),
                    volatility_20d=float(row["volatility_20d"]),
                    distance_from_20d_high=float(row["distance_from_20d_high"]),
                    relative_volume=float(row["relative_volume"]),
                    spread_bps=float(row["spread_bps"]),
                )
            )
        return snapshots


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def run_atlas(config: AtlasConfig, project_root: Path = Path(".")) -> AtlasRunResult:
    stocks = _read_universe(config.stock_universe_path, "stock")
    crypto = _read_universe(config.crypto_universe_path, "crypto")
    snapshots = stocks + crypto
    eligible = [
        item
        for item in snapshots
        if item.price >= config.minimum_price
        and item.price * item.average_daily_volume >= config.minimum_daily_dollar_volume
    ]
    scores = sorted(
        (score_opportunity(item) for item in eligible),
        key=lambda item: (item.alpha_score, item.confidence),
        reverse=True,
    )[: config.top_candidates]

    config.output_root.mkdir(parents=True, exist_ok=True)
    ranking_path = config.output_root / "opportunity_ranking.json"
    dashboard_path = config.output_root / "atlas_dashboard.json"
    manifest_path = config.output_root / "experiment_manifest.json"
    _write_json(ranking_path, [asdict(item) for item in scores])

    input_fingerprints = {
        str(path): file_sha256(path)
        for path in (config.stock_universe_path, config.crypto_universe_path)
        if path.exists()
    }
    artifacts = {
        "opportunity_ranking": str(ranking_path),
        "dashboard": str(dashboard_path),
        "manifest": str(manifest_path),
    }
    manifest = create_manifest(
        project_root=project_root,
        platform_version=PLATFORM_VERSION,
        config=config,
        input_fingerprints=input_fingerprints,
        artifacts=artifacts,
    )
    _write_json(manifest_path, asdict(manifest))

    counts: dict[str, int] = {}
    for score in scores:
        counts[score.strategy] = counts.get(score.strategy, 0) + 1
    diagnostics_passed = (
        bool(snapshots) and bool(eligible) and manifest.baseline_fingerprint is not None
    )
    dashboard = {
        "platform_version": PLATFORM_VERSION,
        "experiment_id": manifest.experiment_id,
        "scanned_assets": len(snapshots),
        "eligible_assets": len(eligible),
        "ranked_assets": len(scores),
        "strategy_counts": counts,
        "diagnostics_passed": diagnostics_passed,
        "paper_trading_enabled": config.paper_trading_enabled,
        "live_trading_enabled": config.live_trading_enabled,
        "baseline_locked": manifest.baseline_fingerprint is not None,
    }
    _write_json(dashboard_path, dashboard)

    return AtlasRunResult(
        experiment_id=manifest.experiment_id,
        scanned_assets=len(snapshots),
        eligible_assets=len(eligible),
        ranked_assets=len(scores),
        top_strategy_counts=counts,
        diagnostics_passed=diagnostics_passed,
        approved_for_paper_trading=False,
        approved_for_live_trading=False,
        output=str(config.output_root),
        artifacts=artifacts,
    )
