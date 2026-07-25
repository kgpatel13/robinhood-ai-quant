from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase11.model_engine import run_model_intelligence
from src.research.phase11.model_models import ModelIntelligenceConfig


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run Phase 11.3-11.9 baseline model intelligence and final research signoff"
    )
    result.add_argument(
        "--dataset", type=Path, default=Path("data/ml_dataset/training_dataset.parquet")
    )
    result.add_argument(
        "--label-signoff",
        type=Path,
        default=Path("reports/phase11_label_intelligence/phase11_label_signoff.json"),
    )
    result.add_argument("--output", type=Path, default=Path("reports/phase11_model_intelligence"))
    result.add_argument("--maximum-rows-per-horizon", type=int, default=120_000)
    result.add_argument("--minimum-train-rows", type=int, default=2_000)
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_model_intelligence(
        ModelIntelligenceConfig(
            dataset_path=args.dataset,
            label_signoff_path=args.label_signoff,
            output_root=args.output,
            maximum_rows_per_horizon=args.maximum_rows_per_horizon,
            minimum_train_rows=args.minimum_train_rows,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
