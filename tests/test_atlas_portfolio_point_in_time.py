from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.atlas.portfolio.point_in_time import (
    PointInTimeConfig,
    build_point_in_time_snapshots,
    load_snapshot_candidates,
    resolve_snapshot,
)


def _write_history(path: Path, start: str, periods: int, base: float) -> None:
    dates = pd.bdate_range(start, periods=periods)
    frame = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [base + index * 0.1 for index in range(periods)],
            "high": [base + index * 0.1 + 1.0 for index in range(periods)],
            "low": [base + index * 0.1 - 1.0 for index in range(periods)],
            "close": [base + index * 0.1 for index in range(periods)],
            "volume": [1_000_000 + index for index in range(periods)],
        }
    )
    frame.to_csv(path, index=False)


def test_builds_deterministic_leakage_free_snapshots(tmp_path: Path) -> None:
    history = tmp_path / "daily"
    history.mkdir()
    _write_history(history / "stock__AAA.csv", "2024-01-01", 180, 20.0)
    _write_history(history / "stock__BBB.csv", "2024-01-01", 180, 30.0)
    output = tmp_path / "pit"
    config = PointInTimeConfig(
        minimum_history_observations=60,
        rebalance_observations=30,
        momentum_long=50,
        volatility_window=20,
        trend_window=20,
    )
    first = build_point_in_time_snapshots(history, output, None, config)
    first_hashes = [record.sha256 for record in first.snapshots]
    second = build_point_in_time_snapshots(history, output, None, config)
    assert first_hashes == [record.sha256 for record in second.snapshots]
    assert first.leakage_audit["passed"] is True
    assert len(first.snapshots) >= 2


def test_snapshot_candidates_and_resolution(tmp_path: Path) -> None:
    history = tmp_path / "daily"
    history.mkdir()
    _write_history(history / "stock__AAA.csv", "2024-01-01", 140, 20.0)
    output = tmp_path / "pit"
    config = PointInTimeConfig(
        minimum_history_observations=60,
        rebalance_observations=30,
        momentum_long=50,
        volatility_window=20,
        trend_window=20,
    )
    result = build_point_in_time_snapshots(history, output, None, config)
    resolved = resolve_snapshot(output / "snapshots", result.snapshots[-1].as_of)
    candidates = load_snapshot_candidates(resolved)
    assert candidates
    assert candidates[0].asset_id == "stock:AAA"
    assert candidates[0].alpha_percentile == 1.0
