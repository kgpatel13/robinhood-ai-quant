from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.research.phase10.advanced_validation import (
    FinalPromotionRules,
    bootstrap_confidence,
    cross_sectional_rank_analysis,
    feature_predictiveness,
    feature_stability,
    final_promotion_decisions,
    final_research_signoff,
    label_quality_analysis,
    time_decay_analysis,
)
from src.research.phase10.replay import FEATURE_COLUMNS
from src.research.phase10.robustness import (
    PromotionRules,
    leakage_audit,
    promotion_decisions,
    rolling_walk_forward_validation,
    transaction_cost_stress,
    window_stability,
)


def _write(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run final Phase 10.x validation from an existing signal replay"
    )
    parser.add_argument("--signal-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/phase10_4_validation"))
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
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
    labels = label_quality_analysis(replay)
    feature_ic = feature_predictiveness(replay, FEATURE_COLUMNS)
    feature_summary = feature_stability(feature_ic)
    rank_analysis = cross_sectional_rank_analysis(replay)
    decay = time_decay_analysis(replay)
    confidence = bootstrap_confidence(replay, samples=args.bootstrap_samples)
    final_decisions = final_promotion_decisions(
        decisions,
        decay,
        confidence,
        rank_analysis,
        feature_summary,
        FinalPromotionRules(),
    )
    data_cutoff = str(pd.to_datetime(replay["signal_timestamp"], utc=True).max())
    signoff = final_research_signoff(final_decisions, leakage, "0.10.4", data_cutoff)

    outputs = {
        "rolling_walk_forward_results.csv": rolling,
        "window_stability.csv": stability,
        "transaction_cost_stress.csv": costs,
        "leakage_audit.csv": leakage,
        "promotion_decisions.csv": decisions,
        "label_quality_analysis.csv": labels,
        "feature_predictiveness.csv": feature_ic,
        "feature_stability.csv": feature_summary,
        "cross_sectional_rank_analysis.csv": rank_analysis,
        "time_decay_analysis.csv": decay,
        "bootstrap_confidence.csv": confidence,
        "final_promotion_decisions.csv": final_decisions,
    }
    for name, frame in outputs.items():
        _write(frame, args.output / name)
    (args.output / "phase10_final_signoff.json").write_text(
        json.dumps(signoff, indent=2), encoding="utf-8"
    )
    print(json.dumps(signoff, indent=2))


if __name__ == "__main__":
    main()
