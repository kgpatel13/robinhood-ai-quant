from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase12.engine import run_phase12
from src.research.phase12.models import Phase12Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run Phase 12 walk-forward research and economic validation"
    )
    result.add_argument(
        "--dataset", type=Path, default=Path("data/ml_dataset/training_dataset.parquet")
    )
    result.add_argument(
        "--phase11-champions",
        type=Path,
        default=Path("reports/phase11_model_intelligence/champion_models.csv"),
    )
    result.add_argument("--output", type=Path, default=Path("reports/phase12_research_validation"))
    result.add_argument("--horizons", nargs="+", type=int, default=[20, 10])
    result.add_argument("--maximum-rows-per-horizon", type=int, default=160_000)
    result.add_argument("--folds", type=int, default=4)
    result.add_argument("--minimum-train-timestamps", type=int, default=300)
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase12(
        Phase12Config(
            dataset_path=args.dataset,
            phase11_champions_path=args.phase11_champions,
            output_root=args.output,
            horizons=tuple(args.horizons),
            maximum_rows_per_horizon=args.maximum_rows_per_horizon,
            folds=args.folds,
            minimum_train_timestamps=args.minimum_train_timestamps,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
