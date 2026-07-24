from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.research.phase7.promotion_metrics import enrich_promotion_metrics


def _write_candidate(root: Path) -> Path:
    tournament = root / "strategy_tournament.csv"
    pd.DataFrame([{"strategy": "demo", "symbol": "SPY"}]).to_csv(tournament, index=False)
    candidate = root / "demo" / "SPY"
    candidate.mkdir(parents=True)
    count = 320
    pd.DataFrame(
        {
            "close": [100.0 + index * 0.20 for index in range(count)],
            "equity": [100_000.0 + index * 100.0 for index in range(count)],
        }
    ).to_csv(candidate / "oos_equity.csv", index=False)
    windows = [
        {"metrics": {"strategy_total_return": value}}
        for value in [0.05, 0.03, -0.01, 0.04, 0.02, 0.01]
    ]
    (candidate / "windows.json").write_text(json.dumps(windows), encoding="utf-8")
    return tournament


def test_enrichment_computes_non_placeholder_metrics(tmp_path: Path) -> None:
    tournament = _write_candidate(tmp_path)
    enriched, regimes, monte_carlo = enrich_promotion_metrics(
        pd.read_csv(tournament), tournament, runs=200, seed=7, confidence=0.95
    )
    row = enriched.iloc[0]
    assert float(row["regime_score"]) > 0.0
    assert int(row["regime_coverage"]) > 0
    assert float(row["monte_carlo_survival"]) > 0.0
    assert int(row["monte_carlo_observations"]) == 6
    assert regimes[0]["regime_metric_source"] == "oos_equity"
    assert monte_carlo[0]["monte_carlo_metric_source"] == "walk_forward_windows"


def test_enrichment_marks_missing_evidence(tmp_path: Path) -> None:
    tournament = tmp_path / "strategy_tournament.csv"
    frame = pd.DataFrame([{"strategy": "demo", "symbol": "SPY"}])
    frame.to_csv(tournament, index=False)
    enriched, _, _ = enrich_promotion_metrics(frame, tournament, runs=100, seed=1, confidence=0.95)
    row = enriched.iloc[0]
    assert row["regime_metric_source"] == "missing"
    assert row["monte_carlo_metric_source"] == "missing"
    assert float(row["regime_score"]) == 0.0
    assert float(row["monte_carlo_survival"]) == 0.0
