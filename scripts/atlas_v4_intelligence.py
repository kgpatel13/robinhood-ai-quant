from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.atlas.portfolio.analytics import (
    AnalyticsConfig,
    analyze_portfolio,
    build_scorecard,
    load_return_matrix,
    read_market_caps,
    write_intelligence_reports,
)
from src.atlas.portfolio.core import TargetPosition
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Phase 4.2.2 portfolio intelligence")
    parser.add_argument("--portfolio", type=Path, default=Path("reports/atlas_v4/portfolio.json"))
    parser.add_argument("--history", type=Path, default=Path("data/market/daily"))
    parser.add_argument("--metadata", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/SPY.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/atlas_v4/intelligence"))
    parser.add_argument("--risk-free-rate", type=float, default=0.04)
    parser.add_argument("--confidence-level", type=float, default=0.95)
    parser.add_argument("--minimum-observations", type=int, default=60)
    return parser


def _read_targets(path: Path) -> list[TargetPosition]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("positions", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Portfolio must contain a positions list")
    return [TargetPosition(**row) for row in rows]


def _read_benchmark(path: Path) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=float)
    frame = pd.read_csv(path)
    date_column = "timestamp" if "timestamp" in frame.columns else "date"
    close_column = "close" if "close" in frame.columns else "Close"
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[close_column] = pd.to_numeric(frame[close_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, close_column]).sort_values(date_column)
    return frame.set_index(date_column)[close_column].pct_change(fill_method=None).dropna()


def main() -> int:
    args = build_parser().parse_args()
    targets = _read_targets(args.portfolio)
    returns, coverage, missing = load_return_matrix(targets, args.history)
    config = AnalyticsConfig(
        risk_free_rate=args.risk_free_rate,
        confidence_level=args.confidence_level,
        minimum_observations=args.minimum_observations,
    )
    intelligence = analyze_portfolio(
        targets,
        returns,
        coverage,
        config,
        benchmark_returns=_read_benchmark(args.benchmark),
        market_caps=read_market_caps(args.metadata),
    )
    scorecard = build_scorecard(intelligence)
    artifacts = write_intelligence_reports(intelligence, scorecard, returns, args.output)
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "position_count": len(targets),
        "missing_history": list(missing),
        "intelligence": asdict(intelligence),
        "scorecard": asdict(scorecard),
        "artifacts": artifacts,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
