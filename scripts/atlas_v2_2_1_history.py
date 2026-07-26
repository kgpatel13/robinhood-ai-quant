from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas.engine import load_config
from src.atlas.history import update_history


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Atlas AI daily historical market data")
    parser.add_argument("--config", type=Path, default=Path("config/atlas_v2.yaml"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = update_history(load_config(args.config))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
