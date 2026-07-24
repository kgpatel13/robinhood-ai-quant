from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.research.phase8.diagnostics import build_gate_diagnostics, write_diagnostic_reports
from src.research.phase8.experiment_store import ExperimentStore
from src.research.phase8.features import build_feature_snapshot
from src.research.phase8.models import CandidateDefinition
from src.research.phase8.ranking import build_candidate_ranking
from src.research.phase8.search_space import candidate_id, generate_strategy_candidates
from src.research.phase8.stability import apply_neighborhood_stability


def test_candidate_id_is_deterministic() -> None:
    first = candidate_id("moving_average_cross", {"fast_window": 20, "slow_window": 100})
    second = candidate_id("moving_average_cross", {"slow_window": 100, "fast_window": 20})
    assert first == second


def test_generate_candidates_respects_limit() -> None:
    candidates = generate_strategy_candidates(
        "moving_average_cross", maximum=3, method="hybrid", seed=42
    )
    assert 1 <= len(candidates) <= 3
    assert all(item.strategy == "moving_average_cross" for item in candidates)


def test_diagnostics_gap_direction(tmp_path: Path) -> None:
    report = tmp_path / "promotion.json"
    report.write_text(
        json.dumps(
            [
                {
                    "strategy": "s1",
                    "symbol": "SPY",
                    "gates": [
                        {
                            "name": "minimum_sharpe",
                            "passed": False,
                            "actual": 0.5,
                            "threshold": 0.75,
                            "comparison": ">=",
                        },
                        {
                            "name": "maximum_drawdown",
                            "passed": True,
                            "actual": -0.2,
                            "threshold": -0.3,
                            "comparison": ">=",
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    rows = build_gate_diagnostics(report)
    assert rows[0].gap == -0.25
    artifacts = write_diagnostic_reports(report, tmp_path / "out")
    assert Path(artifacts["gate_failure_matrix"]).exists()


def test_experiment_store_round_trip(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path / "experiments.sqlite3")
    store.create_experiment("e1", {"seed": 42}, tmp_path)
    candidate = CandidateDefinition("c1", "rsi_mean_reversion", {"window": 14}, "default")
    store.upsert_candidate("e1", candidate, "COMPLETED")
    assert store.candidate_status("e1", "c1") == "COMPLETED"


def test_feature_snapshot_has_lagged_features() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=250, freq="D"),
            "close": [100.0 + index for index in range(250)],
        }
    )
    result = build_feature_snapshot(frame)
    assert {"momentum_21d", "volatility_21d", "trend_50_200", "drawdown"}.issubset(result.columns)


def test_neighborhood_stability() -> None:
    frame = pd.DataFrame(
        [
            {
                "strategy": "a",
                "base_strategy": "ma",
                "symbol": "SPY",
                "parameters_json": json.dumps({"fast": 10, "slow": 50}),
                "oos_sharpe_ratio": 1.0,
            },
            {
                "strategy": "b",
                "base_strategy": "ma",
                "symbol": "SPY",
                "parameters_json": json.dumps({"fast": 11, "slow": 50}),
                "oos_sharpe_ratio": 0.9,
            },
        ]
    )
    result = apply_neighborhood_stability(frame, minimum_neighbors=1)
    assert result["parameter_stability"].tolist() == [1.0, 1.0]


def test_explainable_ranking() -> None:
    frame = pd.DataFrame(
        [
            {
                "strategy": "a",
                "symbol": "SPY",
                "composite_score": 80.0,
                "paper_eligible": False,
                "failed_gates": "sharpe,alpha",
            },
            {
                "strategy": "b",
                "symbol": "SPY",
                "composite_score": 75.0,
                "paper_eligible": True,
                "failed_gates": "",
            },
        ]
    )
    result = build_candidate_ranking(frame)
    assert result.iloc[0]["strategy"] == "b"
    assert "Passed every" in str(result.iloc[0]["explanation"])
