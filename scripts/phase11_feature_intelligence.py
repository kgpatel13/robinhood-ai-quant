from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase11.intelligence_engine import run_feature_intelligence
from src.research.phase11.intelligence_models import FeatureIntelligenceConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 11.1 feature intelligence and dataset diagnostics"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/ml_dataset/training_dataset.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/phase11_feature_intelligence"),
    )
    parser.add_argument("--maximum-rows", type=int, default=200_000)
    parser.add_argument("--correlation-threshold", type=float, default=0.90)
    parser.add_argument("--drift-threshold", type=float, default=0.35)
    args = parser.parse_args()
    config = FeatureIntelligenceConfig(
        dataset_path=args.dataset,
        output_root=args.output,
        maximum_analysis_rows=args.maximum_rows,
        correlation_threshold=args.correlation_threshold,
        drift_threshold=args.drift_threshold,
    )
    result = run_feature_intelligence(config)
    print(json.dumps(result.__dict__, indent=2, default=str))
    if not result.diagnostics_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
