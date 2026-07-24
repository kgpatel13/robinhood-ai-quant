from __future__ import annotations

import pandas as pd


def build_candidate_ranking(leaderboard: pd.DataFrame) -> pd.DataFrame:
    frame = leaderboard.copy()
    failed = frame.get("failed_gates", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["failed_gate_count"] = failed.map(lambda value: 0 if not value else len(value.split(",")))
    frame["readiness_score"] = (
        pd.to_numeric(frame["composite_score"], errors="coerce").fillna(0.0)
        - frame["failed_gate_count"] * 5.0
    )
    frame["explanation"] = frame.apply(
        lambda row: (
            "Passed every promotion gate."
            if int(row["failed_gate_count"]) == 0
            else f"Failed {int(row['failed_gate_count'])} gate(s): {row['failed_gates']}"
        ),
        axis=1,
    )
    return frame.sort_values(
        ["paper_eligible", "readiness_score", "composite_score"],
        ascending=[False, False, False],
    )
