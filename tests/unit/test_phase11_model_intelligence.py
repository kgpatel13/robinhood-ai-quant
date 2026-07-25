from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase11.model_analysis import (
    chronological_sample,
    purged_temporal_split,
    threshold_economics,
)
from src.research.phase11.model_engine import run_model_intelligence
from src.research.phase11.model_models import ModelIntelligenceConfig


def _model_frame(rows: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    timestamps = pd.date_range("2020-01-01", periods=rows // 2, freq="D", tz="UTC")
    records: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(("AAA", "BBB")):
        for index, timestamp in enumerate(timestamps):
            signal = np.sin(index / 17.0) + symbol_index * 0.1
            net_return = 0.004 * signal + rng.normal(0.0, 0.01)
            record: dict[str, object] = {
                "timestamp": timestamp,
                "symbol": symbol,
                "asset_class": "stock" if symbol == "AAA" else "crypto",
                "regime": "bull" if index % 3 else "sideways",
                "holding_period": 10,
                "positive_return_label": int(net_return > 0.0),
                "net_forward_return": net_return,
            }
            for feature_index, feature in enumerate(FEATURE_COLUMNS):
                record[feature] = signal + rng.normal(0.0, 0.1 + feature_index * 0.001)
            records.append(record)
    return pd.DataFrame(records)


def test_temporal_split_is_strictly_chronological() -> None:
    split = purged_temporal_split(_model_frame(), 0.60, 0.20, 5, 3)
    assert split.train["timestamp"].max() < split.validation["timestamp"].min()
    assert split.validation["timestamp"].max() < split.test["timestamp"].min()
    assert split.audit["chronology_passed"].all()


def test_chronological_sample_preserves_time_coverage() -> None:
    frame = _model_frame()
    sample = chronological_sample(frame, 200)
    assert len(sample) <= 200
    assert sample["timestamp"].min() == frame["timestamp"].min()
    assert sample["timestamp"].max() == frame["timestamp"].max()


def test_threshold_economics_is_bounded() -> None:
    frame = _model_frame(400)
    probabilities = np.linspace(0.0, 1.0, len(frame))
    result = threshold_economics(frame, probabilities, (0.5, 0.7))
    assert result["trade_rate"].between(0.0, 1.0).all()
    assert result["win_rate"].between(0.0, 1.0).all()
    assert result["maximum_drawdown"].between(0.0, 1.0).all()


def test_full_model_intelligence_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _model_frame(2400)
    monkeypatch.setattr(pd, "read_parquet", lambda _: frame)
    config = ModelIntelligenceConfig(
        dataset_path=tmp_path / "dataset.parquet",
        label_signoff_path=tmp_path / "missing.json",
        output_root=tmp_path / "reports",
        maximum_rows_per_horizon=2_400,
        minimum_train_rows=500,
        purge_bars=5,
        embargo_bars=3,
        minimum_test_trades=1,
        maximum_test_drawdown=1.0,
    )
    result = run_model_intelligence(config)
    assert result.horizons_analyzed == 1
    assert result.models_trained == 5
    assert result.champions_selected == 1
    assert result.diagnostics_passed
    assert (tmp_path / "reports" / "phase11_final_signoff.json").exists()
