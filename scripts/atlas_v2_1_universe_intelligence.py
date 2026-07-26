from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas.engine import load_config
from src.atlas.universe import UniverseDownloadError, update_universe


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the Atlas AI 2.1 asset universe registry")
    parser.add_argument("--config", type=Path, default=Path("config/atlas_v2.yaml"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stocks-only", action="store_true")
    mode.add_argument("--crypto-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = load_config(args.config)
    try:
        result = update_universe(
            config,
            include_stocks=not args.crypto_only,
            include_crypto=not args.stocks_only,
        )
    except UniverseDownloadError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
