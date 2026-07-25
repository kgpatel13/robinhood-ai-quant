from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase11.label_engine import run_label_intelligence
from src.research.phase11.label_models import LabelIntelligenceConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Run Phase 11.2.2 calibrated label intelligence and target validation")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/ml_dataset/training_dataset.parquet")
    )
    parser.add_argument("--output", type=Path, default=Path("reports/phase11_label_intelligence"))
    parser.add_argument("--maximum-rows", type=int, default=300_000)
    parser.add_argument("--minimum-horizon-rows", type=int, default=5_000)
    parser.add_argument("--minimum-positive-rate", type=float, default=0.20)
    parser.add_argument("--maximum-positive-rate", type=float, default=0.80)
    parser.add_argument("--maximum-extreme-return-fraction", type=float, default=0.02)
    parser.add_argument("--extreme-return-threshold", type=float, default=0.25)
    parser.add_argument("--minimum-quality-index", type=float, default=0.55)
    parser.add_argument("--secondary-quality-index", type=float, default=0.85)
    parser.add_argument("--primary-quality-index", type=float, default=0.90)
    args = parser.parse_args()
    result = run_label_intelligence(
        LabelIntelligenceConfig(
            dataset_path=args.dataset,
            output_root=args.output,
            maximum_analysis_rows=args.maximum_rows,
            minimum_horizon_rows=args.minimum_horizon_rows,
            minimum_positive_rate=args.minimum_positive_rate,
            maximum_positive_rate=args.maximum_positive_rate,
            maximum_extreme_return_fraction=args.maximum_extreme_return_fraction,
            extreme_return_threshold=args.extreme_return_threshold,
            minimum_quality_index=args.minimum_quality_index,
            secondary_quality_index=args.secondary_quality_index,
            primary_quality_index=args.primary_quality_index,
        )
    )
    print(json.dumps(result.__dict__, indent=2, default=str))
    if not result.diagnostics_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
