from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase18.engine import run_phase18
from src.research.phase18.models import Phase18Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run Phase 18.6 institutional validation optimizer"
    )
    result.add_argument(
        "--phase17-scores",
        type=Path,
        default=Path("reports/phase17_execution_intelligence/execution_scores.csv"),
    )
    result.add_argument(
        "--phase17-equity",
        type=Path,
        default=Path("reports/phase17_execution_intelligence/phase17_equity_curve.csv"),
    )
    result.add_argument(
        "--phase17-executed",
        type=Path,
        default=Path("reports/phase17_execution_intelligence/phase17_executed_trades.csv"),
    )
    result.add_argument(
        "--output",
        type=Path,
        default=Path("reports/phase18_6_institutional_validation"),
    )
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase18(
        Phase18Config(
            phase17_scores_path=args.phase17_scores,
            phase17_equity_path=args.phase17_equity,
            phase17_executed_path=args.phase17_executed,
            output_root=args.output,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
