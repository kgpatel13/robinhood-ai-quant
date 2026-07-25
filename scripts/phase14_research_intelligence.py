from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.research.phase14.engine import run_phase14
from src.research.phase14.models import Phase14Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run Phase 14 research intelligence")
    result.add_argument(
        "--executed-trades",
        type=Path,
        default=Path("reports/phase13_portfolio_engine/executed_trades.csv"),
    )
    result.add_argument(
        "--rejected-signals",
        type=Path,
        default=Path("reports/phase13_portfolio_engine/rejected_signals.csv"),
    )
    result.add_argument(
        "--equity-curve",
        type=Path,
        default=Path("reports/phase13_portfolio_engine/portfolio_equity_curve.csv"),
    )
    result.add_argument(
        "--output", type=Path, default=Path("reports/phase14_research_intelligence")
    )
    result.add_argument("--risk-free-rate", type=float, default=0.0)
    return result


def main() -> None:
    args = parser().parse_args()
    result = run_phase14(
        Phase14Config(
            executed_trades_path=args.executed_trades,
            rejected_signals_path=args.rejected_signals,
            equity_curve_path=args.equity_curve,
            output_root=args.output,
            risk_free_rate=args.risk_free_rate,
        )
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
