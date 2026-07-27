from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from src.atlas.portfolio.metadata import (
    enrich_metadata,
    read_asset_identities,
    read_metadata,
    write_metadata,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Phase 4.2.1 market metadata enrichment")
    parser.add_argument("--assets", type=Path, default=Path("reports/atlas_v3/ranked_assets.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay-seconds", type=float, default=0.10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    identities = read_asset_identities(args.assets)
    existing = read_metadata(args.output)

    def progress(index: int, total: int, record: object) -> None:
        status = getattr(record, "status", "unknown")
        symbol = getattr(record, "symbol", "unknown")
        print(f"[{index}/{total}] {symbol}: {status}")

    records = enrich_metadata(
        identities,
        existing,
        force=args.force,
        limit=args.limit,
        delay_seconds=max(args.delay_seconds, 0.0),
        on_progress=progress,
    )
    write_metadata(args.output, records.values())
    statuses = Counter(item.status for item in records.values())
    stocks = [item for item in records.values() if item.asset_class == "stock"]
    stock_count = len(stocks)
    sector_count = sum(bool(item.sector) for item in stocks)
    industry_count = sum(bool(item.industry) for item in stocks)
    country_count = sum(bool(item.country) for item in stocks)
    market_cap_count = sum(item.market_cap is not None for item in stocks)

    def coverage(populated: int) -> float:
        return populated / stock_count if stock_count else 0.0

    summary = {
        "complete": True,
        "platform_version": __version__,
        "asset_count": len(identities),
        "metadata_count": len(records),
        "stock_count": stock_count,
        "sector_coverage": coverage(sector_count),
        "industry_coverage": coverage(industry_count),
        "country_coverage": coverage(country_count),
        "market_cap_coverage": coverage(market_cap_count),
        "statuses": dict(sorted(statuses.items())),
        "output": str(args.output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
