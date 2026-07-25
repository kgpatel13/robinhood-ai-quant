from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.research.phase10.robustness import (
    PromotionRules,
    leakage_audit,
    promotion_decisions,
    research_signoff,
    rolling_walk_forward_validation,
    transaction_cost_stress,
    window_stability,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 10.4 final robustness validation from signal replay"
    )
    parser.add_argument("--signal-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/phase10_2_validation"))
    args = parser.parse_args()

    replay = pd.read_csv(args.signal_replay)
    args.output.mkdir(parents=True, exist_ok=True)
    thresholds = {
        "stock": (50.0, 55.0, 60.0, 62.0, 65.0, 70.0, 75.0),
        "etf": (50.0, 55.0, 60.0, 62.0, 65.0, 70.0, 75.0),
        "crypto": (40.0, 45.0, 50.0, 55.0, 60.0, 64.0, 70.0, 78.0),
    }
    minimum_trades = {"stock": 20, "etf": 20, "crypto": 20}
    rolling = rolling_walk_forward_validation(replay, thresholds, minimum_trades)
    stability = window_stability(rolling)
    costs = transaction_cost_stress(
        replay,
        {
            "stock": {"optimistic": 0.0, "base": 5.0, "stress": 10.0},
            "etf": {"optimistic": 0.0, "base": 3.0, "stress": 7.0},
            "crypto": {"optimistic": 0.0, "base": 25.0, "stress": 50.0},
        },
    )
    leakage = leakage_audit(replay)
    decisions = promotion_decisions(stability, PromotionRules())
    data_cutoff = str(pd.to_datetime(replay["signal_timestamp"], utc=True).max())
    signoff = research_signoff(decisions, leakage, "0.10.4", data_cutoff)

    rolling.to_csv(args.output / "rolling_walk_forward_results.csv", index=False)
    stability.to_csv(args.output / "window_stability.csv", index=False)
    costs.to_csv(args.output / "transaction_cost_stress.csv", index=False)
    leakage.to_csv(args.output / "leakage_audit.csv", index=False)
    decisions.to_csv(args.output / "promotion_decisions.csv", index=False)
    (args.output / "phase10_research_signoff.json").write_text(
        json.dumps(signoff, indent=2), encoding="utf-8"
    )
    print(json.dumps(signoff, indent=2))


if __name__ == "__main__":
    main()
