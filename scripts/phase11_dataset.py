from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase11.engine import build_phase11_dataset
from src.research.phase11.models import Phase11Config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 11 point-in-time ML dataset")
    parser.add_argument("--data-root", type=Path, default=Path("data/validated"))
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/ml_dataset/training_dataset.parquet"),
    )
    parser.add_argument("--output", type=Path, default=Path("reports/phase11_dataset"))
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--asset-classes", nargs="*", choices=("stock", "etf", "crypto"))
    parser.add_argument("--holding-periods", nargs="*", type=int)
    parser.add_argument("--stride", type=int, default=1)
    args = parser.parse_args()
    defaults = Phase11Config()
    config = Phase11Config(
        data_root=args.data_root,
        dataset_path=args.dataset,
        output_root=args.output,
        symbols=tuple(args.symbols or ()),
        asset_classes=tuple(args.asset_classes or defaults.asset_classes),
        holding_periods=tuple(args.holding_periods or defaults.holding_periods),
        observation_stride=args.stride,
    )
    result = build_phase11_dataset(config)
    print(json.dumps(result.__dict__, indent=2, default=str))
    if not result.audit_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
