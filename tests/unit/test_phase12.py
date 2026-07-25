from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase12.analysis import (
    expanding_walk_forward_folds,
    fit_platt_calibrator,
    realistic_portfolio_simulation,
)
from src.research.phase12.engine import run_phase12
from src.research.phase12.models import Phase12Config


def _frame(rows_per_symbol: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(12)
    timestamps = pd.date_range("2020-01-01", periods=rows_per_symbol, freq="D", tz="UTC")
    records: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(("AAA", "BBB")):
        for index, timestamp in enumerate(timestamps):
            signal = np.sin(index / 20.0) + 0.05 * symbol_index
            result = 0.006 * signal + rng.normal(0.0, 0.01)
            record: dict[str, object] = {
                "timestamp": timestamp,
                "symbol": symbol,
                "asset_class": "stock",
                "regime": "bull",
                "holding_period": 20,
                "positive_return_label": int(result > 0.0),
                "net_forward_return": result,
            }
            for feature_index, feature in enumerate(FEATURE_COLUMNS):
                record[feature] = signal + rng.normal(0.0, 0.15 + feature_index * 0.001)
            records.append(record)
    return pd.DataFrame(records)


def test_walk_forward_folds_are_chronological() -> None:
    folds = expanding_walk_forward_folds(_frame(), 2, 150, 0.15, 0.15, 5, 3)
    assert len(folds) == 2
    assert all(bool(fold.audit["chronology_passed"]) for fold in folds)


def test_platt_calibration_is_bounded() -> None:
    labels = pd.Series([0, 0, 1, 1])
    calibrator = fit_platt_calibrator(np.array([0.1, 0.3, 0.7, 0.9]), labels)
    values = calibrator.transform(np.array([0.0, 0.5, 1.0]))
    assert np.all(values >= 0.0)
    assert np.all(values <= 1.0)


def test_simulator_prevents_overlapping_symbol_trades() -> None:
    frame = _frame(100).loc[lambda value: value["symbol"] == "AAA"].reset_index(drop=True)
    probabilities = np.full(len(frame), 0.9)
    metrics, trades = realistic_portfolio_simulation(
        frame,
        probabilities,
        0.5,
        20,
        10_000.0,
        5,
        0.2,
        5.0,
        0.0,
    )
    assert 4 <= len(trades) <= 5
    assert int(metrics["trades"]) == len(trades)
    assert 0.0 <= float(metrics["maximum_drawdown"]) <= 1.0


def test_phase12_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(700)
    monkeypatch.setattr(pd, "read_parquet", lambda _: frame)
    result = run_phase12(
        Phase12Config(
            dataset_path=tmp_path / "dataset.parquet",
            output_root=tmp_path / "reports",
            horizons=(20,),
            maximum_rows_per_horizon=1_400,
            folds=2,
            minimum_train_timestamps=200,
            calibration_fraction=0.15,
            test_fraction=0.15,
            purge_bars=5,
            embargo_bars=3,
            minimum_total_trades=1,
            maximum_drawdown=1.0,
        )
    )
    assert result.horizons_analyzed == 1
    assert result.folds_completed == 2
    assert result.models_trained == 18
    assert result.diagnostics_passed
    assert (tmp_path / "reports" / "phase12_final_signoff.json").exists()
