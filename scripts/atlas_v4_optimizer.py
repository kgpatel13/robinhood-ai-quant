from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atlas.portfolio import PortfolioConfig, read_candidates, read_current_positions
from src.atlas.portfolio.optimizer import (
    OptimizerConfig,
    run_optimizer_suite,
    write_optimizer_reports,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Phase 4.4 institutional optimizer suite")
    parser.add_argument(
        "--ranked-assets",
        type=Path,
        default=Path("reports/atlas_v3/ranked_assets.csv"),
    )
    parser.add_argument("--features", type=Path, default=Path("data/market/features.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument("--history", type=Path, default=Path("data/market/daily"))
    parser.add_argument("--existing-portfolio", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/atlas_v4/optimizer"))
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--cash-reserve", type=float, default=0.05)
    parser.add_argument("--max-positions", type=int, default=25)
    parser.add_argument("--max-position-pct", type=float, default=0.08)
    parser.add_argument("--max-crypto-pct", type=float, default=0.15)
    parser.add_argument("--max-sector-pct", type=float, default=0.25)
    parser.add_argument("--max-industry-pct", type=float, default=0.20)
    parser.add_argument("--minimum-alpha-percentile", type=float, default=0.70)
    parser.add_argument("--minimum-confidence", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--minimum-price", type=float, default=3.0)
    parser.add_argument("--minimum-market-cap", type=float, default=100_000_000.0)
    parser.add_argument("--minimum-liquidity-score", type=float, default=50.0)
    parser.add_argument("--minimum-data-quality-score", type=float, default=80.0)
    parser.add_argument("--maximum-pair-correlation", type=float, default=0.85)
    parser.add_argument("--candidate-buffer", type=int, default=75)
    parser.add_argument("--minimum-history-observations", type=int, default=60)
    parser.add_argument("--transaction-cost-bps", type=float, default=18.0)
    parser.add_argument(
        "--objective",
        choices=("balanced", "sharpe", "diversification", "volatility"),
        default="balanced",
    )
    parser.add_argument(
        "--methods",
        default=(
            "equal,score,inverse_volatility,hybrid,risk_parity,"
            "minimum_variance,maximum_diversification,hrp"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    portfolio_config = PortfolioConfig(
        capital=args.capital,
        cash_reserve_pct=args.cash_reserve,
        max_positions=args.max_positions,
        max_position_pct=args.max_position_pct,
        max_crypto_pct=args.max_crypto_pct,
        max_sector_pct=args.max_sector_pct,
        max_industry_pct=args.max_industry_pct,
        minimum_alpha_percentile=args.minimum_alpha_percentile,
        minimum_confidence=args.minimum_confidence,
        minimum_price=args.minimum_price,
        minimum_market_cap=args.minimum_market_cap,
        minimum_liquidity_score=args.minimum_liquidity_score,
        minimum_data_quality_score=args.minimum_data_quality_score,
        enforce_institutional_eligibility=True,
    )
    optimizer_config = OptimizerConfig(
        methods=tuple(item.strip() for item in args.methods.split(",") if item.strip()),
        objective=args.objective,
        maximum_pair_correlation=args.maximum_pair_correlation,
        candidate_buffer=args.candidate_buffer,
        minimum_history_observations=args.minimum_history_observations,
        transaction_cost_bps=args.transaction_cost_bps,
    )
    candidates = read_candidates(args.ranked_assets, args.features, args.metadata)
    current_positions = read_current_positions(args.existing_portfolio)
    result = run_optimizer_suite(
        candidates,
        args.history,
        portfolio_config,
        optimizer_config,
        current_positions,
    )
    artifacts = write_optimizer_reports(result, args.output)
    selected = next(item for item in result.methods if item.method == result.selected_method)
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "phase": "4.4",
        "candidate_count": len(candidates),
        "selected_asset_count": len(result.selected_assets),
        "selected_method": result.selected_method,
        "selected_method_score": selected.score,
        "successful_methods": [item.method for item in result.methods if item.success],
        "artifacts": artifacts,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
