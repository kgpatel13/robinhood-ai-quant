from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase7 import Phase7Config, run_phase7_selection


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 7 tournament selection and promotion")
    parser.add_argument(
        "--tournament",
        type=Path,
        default=Path("reports/phase6/tournament/strategy_tournament.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("reports/phase7"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--monte-carlo-runs", type=int, default=1000)
    args = parser.parse_args()
    result = run_phase7_selection(
        args.tournament,
        args.output,
        Phase7Config(seed=args.seed, monte_carlo_runs=args.monte_carlo_runs),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
