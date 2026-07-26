from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas.engine import load_config
from src.atlas.market import run_market_intelligence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Atlas AI 2.2 Market Intelligence")
    parser.add_argument("--config", type=Path, default=Path("config/atlas_v2.yaml"))
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_market_intelligence(load_config(args.config), max_workers=args.workers)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
