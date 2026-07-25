from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase13.engine import run_phase13
from src.research.phase13.models import Phase13Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run Phase 13 professional portfolio engine")
    result.add_argument(
        "--trades",
        type=Path,
        default=Path("reports/phase12_research_validation/simulated_trades.csv"),
    )
    result.add_argument("--output", type=Path, default=Path("reports/phase13_portfolio_engine"))
    result.add_argument("--initial-capital", type=float, default=10_000.0)
    result.add_argument("--maximum-open-positions", type=int, default=8)
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase13(
        Phase13Config(
            trades_path=args.trades,
            output_root=args.output,
            initial_capital=args.initial_capital,
            maximum_open_positions=args.maximum_open_positions,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
