from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase15.engine import run_phase15
from src.research.phase15.models import Phase15Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run Phase 15 AI alpha engine")
    result.add_argument(
        "--trades",
        type=Path,
        default=Path("reports/phase12_research_validation/simulated_trades.csv"),
    )
    result.add_argument("--output", type=Path, default=Path("reports/phase15_alpha_engine"))
    result.add_argument("--folds", type=int, default=5)
    result.add_argument("--minimum-train-rows", type=int, default=500)
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase15(
        Phase15Config(
            trades_path=args.trades,
            output_root=args.output,
            folds=args.folds,
            minimum_train_rows=args.minimum_train_rows,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
