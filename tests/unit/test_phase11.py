from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase11.audit import audit_dataset
from src.research.phase11.dataset import build_symbol_dataset
from src.research.phase11.features import build_phase11_features
from src.research.phase11.models import Phase11Config


def _bars(rows: int = 330) -> pd.DataFrame:
    close = [100.0 + index * 0.08 + (index % 9) * 0.04 for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=rows, freq="D", tz="UTC"),
            "symbol": ["TEST"] * rows,
            "open": close,
            "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "adjusted_close": close,
            "volume": [1_000_000.0 + index * 100 for index in range(rows)],
        }
    )


def test_phase11_dataset_uses_future_bars_only_for_labels(tmp_path: Path) -> None:
    config = Phase11Config(dataset_path=tmp_path / "dataset.parquet", output_root=tmp_path)
    dataset = build_symbol_dataset(build_phase11_features(_bars()), "stock", config)
    assert not dataset.empty
    assert (pd.to_datetime(dataset["entry_timestamp"]) > pd.to_datetime(dataset["timestamp"])).all()
    exit_time = pd.to_datetime(dataset["exit_timestamp"])
    entry_time = pd.to_datetime(dataset["entry_timestamp"])
    assert (exit_time >= entry_time).all()


def test_phase11_dataset_contains_all_horizons() -> None:
    config = Phase11Config(observation_stride=10)
    dataset = build_symbol_dataset(build_phase11_features(_bars()), "stock", config)
    assert set(dataset["holding_period"]) == set(config.holding_periods)
    assert dataset["atr_percent"].notna().all()
    assert dataset["drawdown"].notna().all()


def test_phase11_dataset_audit_passes_clean_dataset() -> None:
    config = Phase11Config(observation_stride=10)
    dataset = build_symbol_dataset(build_phase11_features(_bars()), "stock", config)
    audit = audit_dataset(dataset)
    assert bool(audit["passed"].all())


def test_invalid_phase11_configuration() -> None:
    try:
        Phase11Config(warmup_bars=100)
    except ValueError as exc:
        assert "warmup_bars" in str(exc)
    else:
        raise AssertionError("Expected invalid configuration to fail")
