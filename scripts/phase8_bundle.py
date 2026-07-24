from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from src.research.phase8 import Phase8Config, run_phase8_discovery


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 8 robust strategy discovery")
    parser.add_argument("--data-root", type=Path, default=Path("data/validated"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase8"))
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "BTC-USD"])
    parser.add_argument("--strategies", nargs="*", default=[])
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--method", choices=["grid", "random", "hybrid"], default="hybrid")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--monte-carlo-runs", type=int, default=1000)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    base = Phase8Config()
    config = replace(
        base,
        symbols=tuple(args.symbols),
        strategies=tuple(args.strategies),
        max_candidates_per_strategy=args.max_candidates,
        search_method=args.method,
        seed=args.seed,
        workers=args.workers,
        monte_carlo_runs=args.monte_carlo_runs,
        output_root=args.output,
        database_path=args.database or args.output / "experiments.sqlite3",
        resume=not args.no_resume,
    )
    result = run_phase8_discovery(args.data_root, config)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
