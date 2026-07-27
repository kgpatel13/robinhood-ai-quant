from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atlas.portfolio import PortfolioConfig, read_candidates
from src.atlas.portfolio.execution import (
    ExecutionConfig,
    build_orders_from_weights,
    load_daily_dollar_volume,
    simulate_execution,
    write_execution_reports,
)
from src.atlas.portfolio.optimizer import OptimizerConfig, run_optimizer_suite
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas Phase 4.7 institutional execution simulator"
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
        default=Path("reports/atlas_v4/execution"),
    )
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--cash-reserve", type=float, default=0.05)
    parser.add_argument("--max-positions", type=int, default=25)
    parser.add_argument("--max-position-pct", type=float, default=0.08)
    parser.add_argument("--max-crypto-pct", type=float, default=0.15)
    parser.add_argument("--max-sector-pct", type=float, default=0.25)
    parser.add_argument("--max-industry-pct", type=float, default=0.20)
    parser.add_argument("--maximum-participation-rate", type=float, default=0.05)
    parser.add_argument("--execution-horizon-days", type=int, default=1)
    parser.add_argument("--fallback-daily-dollar-volume", type=float, default=1_000_000.0)
    parser.add_argument("--commission-per-order", type=float, default=0.0)
    parser.add_argument("--candidate-buffer", type=int, default=75)
    parser.add_argument("--minimum-history-observations", type=int, default=60)
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
    )
    candidates = read_candidates(args.ranked_assets, args.features, args.metadata)
    suite = run_optimizer_suite(
        candidates,
        args.history,
        portfolio_config,
        optimizer_config,
    )
    selected = next(item for item in suite.methods if item.method == suite.selected_method)
    volume = load_daily_dollar_volume(args.history, list(selected.weights))
    execution_config = ExecutionConfig(
        maximum_participation_rate=args.maximum_participation_rate,
        execution_horizon_days=args.execution_horizon_days,
        fallback_daily_dollar_volume=args.fallback_daily_dollar_volume,
        commission_per_order=args.commission_per_order,
    )
    orders = build_orders_from_weights(
        selected.weights,
        candidates,
        args.capital,
        daily_dollar_volume=volume,
        fallback_daily_dollar_volume=args.fallback_daily_dollar_volume,
    )
    result = simulate_execution(orders, execution_config)
    artifacts = write_execution_reports(result, args.output)
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "phase": "4.7",
        "optimizer_method": suite.selected_method,
        "order_count": result.summary["order_count"],
        "aggregate_fill_ratio": result.summary["aggregate_fill_ratio"],
        "total_execution_cost": result.summary["total_execution_cost"],
        "effective_cost_bps": result.summary["effective_cost_bps"],
        "artifacts": artifacts,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
