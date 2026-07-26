from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas.alpha_pipeline import AlphaPipelineConfig, run_alpha_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Atlas AI v3 factor and alpha ranking")
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/market/features_v2.csv"),
        help="Input feature store CSV",
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=Path("reports/atlas_v3"),
        help="Output report directory",
    )
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--bottom-n", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_alpha_pipeline(
        AlphaPipelineConfig(
            feature_store_path=args.features,
            report_directory=args.reports,
            top_n=args.top_n,
            bottom_n=args.bottom_n,
        )
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
