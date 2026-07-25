from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase11.label_engine import run_label_intelligence
from src.research.phase11.label_models import LabelIntelligenceConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 11.2 label intelligence and target validation"
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/ml_dataset/training_dataset.parquet")
    )
    parser.add_argument("--output", type=Path, default=Path("reports/phase11_label_intelligence"))
    parser.add_argument("--maximum-rows", type=int, default=300_000)
    parser.add_argument("--minimum-quality-index", type=float, default=0.55)
    args = parser.parse_args()
    result = run_label_intelligence(
        LabelIntelligenceConfig(
            dataset_path=args.dataset,
            output_root=args.output,
            maximum_analysis_rows=args.maximum_rows,
            minimum_quality_index=args.minimum_quality_index,
        )
    )
    print(json.dumps(result.__dict__, indent=2, default=str))
    if not result.diagnostics_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
