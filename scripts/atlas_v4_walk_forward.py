from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atlas.portfolio import PortfolioConfig, read_candidates
from src.atlas.portfolio.optimizer import OptimizerConfig
from src.atlas.portfolio.walk_forward import (
    WalkForwardConfig,
    run_walk_forward,
    write_walk_forward_reports,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas Phase 4.5 historical replay and walk-forward validation"
    )
    parser.add_argument(
        "--ranked-assets",
        type=Path,
        default=Path("reports/atlas_v3/ranked_assets.csv"),
    )
    parser.add_argument("--features", type=Path, default=Path("data/market/features.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument("--history", type=Path, default=Path("data/market/daily"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/atlas_v4/walk_forward"),
    )
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--cash-reserve", type=float, default=0.05)
    parser.add_argument("--max-positions", type=int, default=25)
    parser.add_argument("--max-position-pct", type=float, default=0.08)
    parser.add_argument("--max-crypto-pct", type=float, default=0.15)
    parser.add_argument("--max-sector-pct", type=float, default=0.25)
    parser.add_argument("--max-industry-pct", type=float, default=0.20)
    parser.add_argument("--training-observations", type=int, default=252)
    parser.add_argument("--testing-observations", type=int, default=63)
    parser.add_argument("--step-observations", type=int, default=63)
    parser.add_argument("--minimum-windows", type=int, default=2)
    parser.add_argument("--transaction-cost-bps", type=float, default=18.0)
    parser.add_argument("--candidate-buffer", type=int, default=75)
    parser.add_argument("--minimum-history-observations", type=int, default=60)
    parser.add_argument(
        "--method",
        choices=(
            "auto",
            "equal",
            "score",
            "inverse_volatility",
            "hybrid",
            "risk_parity",
            "minimum_variance",
            "maximum_diversification",
            "hrp",
        ),
        default="auto",
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
        enforce_institutional_eligibility=True,
    )
    optimizer_config = OptimizerConfig(
        candidate_buffer=args.candidate_buffer,
        minimum_history_observations=args.minimum_history_observations,
        transaction_cost_bps=args.transaction_cost_bps,
    )
    replay_config = WalkForwardConfig(
        training_observations=args.training_observations,
        testing_observations=args.testing_observations,
        step_observations=args.step_observations,
        minimum_windows=args.minimum_windows,
        method=args.method,
        transaction_cost_bps=args.transaction_cost_bps,
    )
    candidates = read_candidates(args.ranked_assets, args.features, args.metadata)
    result = run_walk_forward(
        candidates,
        args.history,
        portfolio_config,
        optimizer_config,
        replay_config,
    )
    artifacts = write_walk_forward_reports(result, args.output)
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "phase": "4.5",
        "window_count": len(result.windows),
        "method_counts": result.summary["method_counts"],
        "net_compound_return": result.summary["net_compound_return"],
        "all_constraints_passed": result.summary["all_constraints_passed"],
        "artifacts": artifacts,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
