from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas.portfolio import (
    PortfolioConfig,
    PortfolioEngine,
    read_candidates,
    read_current_positions,
    write_reports,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Phase 4 portfolio construction engine")
    parser.add_argument(
        "--ranked-assets",
        type=Path,
        default=Path("reports/atlas_v3/ranked_assets.csv"),
    )
    parser.add_argument("--features", type=Path, default=Path("data/market/features.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument("--existing-portfolio", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/atlas_v4"))
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--cash-reserve", type=float, default=0.05)
    parser.add_argument("--max-positions", type=int, default=25)
    parser.add_argument("--max-position-pct", type=float, default=0.08)
    parser.add_argument("--max-crypto-pct", type=float, default=0.15)
    parser.add_argument("--max-sector-pct", type=float, default=0.25)
    parser.add_argument("--max-industry-pct", type=float, default=0.20)
    parser.add_argument("--minimum-alpha-percentile", type=float, default=0.70)
    parser.add_argument("--minimum-confidence", choices=("low", "medium", "high"), default="medium")
    parser.add_argument(
        "--sizing-method",
        choices=("equal", "score", "volatility", "hybrid"),
        default="hybrid",
    )
    parser.add_argument("--rebalance-threshold-pct", type=float, default=0.005)
    parser.add_argument("--whole-shares", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = PortfolioConfig(
        capital=args.capital,
        cash_reserve_pct=args.cash_reserve,
        max_positions=args.max_positions,
        max_position_pct=args.max_position_pct,
        max_crypto_pct=args.max_crypto_pct,
        max_sector_pct=args.max_sector_pct,
        max_industry_pct=args.max_industry_pct,
        minimum_alpha_percentile=args.minimum_alpha_percentile,
        minimum_confidence=args.minimum_confidence,
        sizing_method=args.sizing_method,
        rebalance_threshold_pct=args.rebalance_threshold_pct,
        fractional_shares=not args.whole_shares,
    )
    candidates = read_candidates(args.ranked_assets, args.features, args.metadata)
    current = read_current_positions(args.existing_portfolio)
    result = PortfolioEngine(config).construct(candidates, current)
    artifacts = write_reports(result, args.output)
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "candidate_count": len(candidates),
        "position_count": len(result.targets),
        "action_count": len(result.actions),
        "config": asdict(config),
        "metrics": asdict(result.metrics),
        "diagnostics": asdict(result.diagnostics),
        "artifacts": artifacts,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
