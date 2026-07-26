from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase17.engine import run_phase17
from src.research.phase17.models import Phase17Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run Phase 17 execution intelligence")
    result.add_argument(
        "--adaptive-allocations",
        type=Path,
        default=Path("reports/phase16_portfolio_intelligence/adaptive_allocations.csv"),
    )
    result.add_argument(
        "--phase16-equity",
        type=Path,
        default=Path("reports/phase16_portfolio_intelligence/phase16_equity_curve.csv"),
    )
    result.add_argument(
        "--phase16-executed",
        type=Path,
        default=Path("reports/phase16_portfolio_intelligence/phase16_executed_trades.csv"),
    )
    result.add_argument(
        "--output", type=Path, default=Path("reports/phase17_execution_intelligence")
    )
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase17(
        Phase17Config(
            adaptive_allocations_path=args.adaptive_allocations,
            phase16_equity_path=args.phase16_equity,
            phase16_executed_path=args.phase16_executed,
            output_root=args.output,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
