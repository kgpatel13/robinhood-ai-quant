from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atlas.portfolio.institutional import (
    InstitutionalConfig,
    run_institutional_analysis,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Phase 4 institutional portfolio controls")
    parser.add_argument(
        "--portfolio",
        type=Path,
        default=Path("reports/atlas_v4/portfolio.json"),
    )
    parser.add_argument(
        "--orders",
        type=Path,
        default=Path("reports/atlas_v4/orders_preview.json"),
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/market/features.csv"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/market/metadata.csv"),
    )
    parser.add_argument("--history", type=Path, default=Path("data/market/daily"))
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/benchmarks/SPY.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/atlas_v4/institutional"),
    )
    parser.add_argument("--minimum-price", type=float, default=3.0)
    parser.add_argument("--minimum-market-cap", type=float, default=100_000_000.0)
    parser.add_argument("--minimum-liquidity-score", type=float, default=50.0)
    parser.add_argument("--minimum-data-quality-score", type=float, default=80.0)
    parser.add_argument("--maximum-pair-correlation", type=float, default=0.85)
    parser.add_argument("--minimum-history-observations", type=int, default=60)
    parser.add_argument("--maximum-absolute-daily-return", type=float, default=0.50)
    parser.add_argument("--monte-carlo-paths", type=int, default=5000)
    parser.add_argument("--bootstrap-block-size", type=int, default=5)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = InstitutionalConfig(
        minimum_price=args.minimum_price,
        minimum_market_cap=args.minimum_market_cap,
        minimum_liquidity_score=args.minimum_liquidity_score,
        minimum_data_quality_score=args.minimum_data_quality_score,
        maximum_pair_correlation=args.maximum_pair_correlation,
        minimum_history_observations=args.minimum_history_observations,
        maximum_absolute_daily_return=args.maximum_absolute_daily_return,
        monte_carlo_paths=args.monte_carlo_paths,
        bootstrap_block_size=args.bootstrap_block_size,
        random_seed=args.random_seed,
    )
    result = run_institutional_analysis(
        args.portfolio,
        args.orders,
        args.features,
        args.metadata,
        args.history,
        args.benchmark,
        args.output,
        config,
    )
    result["platform_version"] = __version__
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
