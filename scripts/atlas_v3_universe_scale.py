from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.atlas.engine import load_config
from src.atlas.history import update_history
from src.atlas.market import run_market_intelligence
from src.atlas.scaling import inspect_history_inventory
from src.atlas.universe import load_registry
from src.atlas.version import __version__


def _parse_limit(value: str) -> int | None:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("limit must be zero or greater")
    return 2_147_483_647 if parsed == 0 else parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Atlas universe-scale research batches")
    parser.add_argument("--config", type=Path, default=Path("config/atlas_v2.yaml"))
    parser.add_argument("--stock-limit", type=_parse_limit, default=1000)
    parser.add_argument("--crypto-limit", type=_parse_limit, default=250)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--minimum-bars", type=int, default=60)
    parser.add_argument("--skip-history", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/atlas_v3/universe_scale_summary.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = load_config(args.config)
    before = inspect_history_inventory(
        load_registry(config.universe_registry_path),
        config.market_history_root,
        minimum_bars=args.minimum_bars,
    )
    history_result = None
    if not args.skip_history:
        history_result = update_history(
            config,
            stock_limit=args.stock_limit,
            crypto_limit=args.crypto_limit,
            offset=args.offset,
            batch_size=args.batch_size,
            workers=args.workers,
        )
    market_result = run_market_intelligence(config, max_workers=args.workers)
    after = inspect_history_inventory(
        load_registry(config.universe_registry_path),
        config.market_history_root,
        minimum_bars=args.minimum_bars,
    )
    complete = market_result.complete and (history_result is None or history_result.complete)
    payload: dict[str, Any] = {
        "platform_version": __version__,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "complete": complete,
        "batch": {
            "stock_limit": args.stock_limit,
            "crypto_limit": args.crypto_limit,
            "offset": args.offset,
            "batch_size": args.batch_size,
            "workers": args.workers,
        },
        "history_before": asdict(before),
        "history_after": asdict(after),
        "history_update": asdict(history_result) if history_result else None,
        "market_intelligence": asdict(market_result),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
