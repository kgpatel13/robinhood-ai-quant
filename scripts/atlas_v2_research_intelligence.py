from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas import load_config, run_atlas


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Atlas AI v2 research intelligence.")
    parser.add_argument("--config", type=Path, default=Path("config/atlas_v2.yaml"))
    args = parser.parse_args()
    result = run_atlas(load_config(args.config))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.diagnostics_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
