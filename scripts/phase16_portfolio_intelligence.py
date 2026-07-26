from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase16.engine import run_phase16
from src.research.phase16.models import Phase16Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run Phase 16 adaptive portfolio intelligence")
    result.add_argument(
        "--selected-trades",
        type=Path,
        default=Path("reports/phase15_alpha_engine/selected_trades.csv"),
    )
    result.add_argument(
        "--phase15-equity",
        type=Path,
        default=Path("reports/phase15_alpha_engine/portfolio_equity_curve.csv"),
    )
    result.add_argument(
        "--phase15-executed",
        type=Path,
        default=Path("reports/phase15_alpha_engine/portfolio_executed_trades.csv"),
    )
    result.add_argument(
        "--output",
        type=Path,
        default=Path("reports/phase16_portfolio_intelligence"),
    )
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase16(
        Phase16Config(
            selected_trades_path=args.selected_trades,
            phase15_equity_path=args.phase15_equity,
            phase15_executed_path=args.phase15_executed,
            output_root=args.output,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
