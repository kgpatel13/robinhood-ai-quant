from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase10.analytics import aggregate
from src.research.phase10.features import build_feature_frame
from src.research.phase10.models import Phase10Config
from src.research.phase10.replay import assign_score_band, replay_symbol


def _bars(rows: int = 320) -> pd.DataFrame:
    close = [100.0 + index * 0.08 + (index % 7) * 0.03 for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2023-01-01", periods=rows, freq="D", tz="UTC"),
            "symbol": ["TEST"] * rows,
            "open": close,
            "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "adjusted_close": close,
            "volume": [1_000_000.0] * rows,
        }
    )


def test_feature_frame_is_point_in_time_usable() -> None:
    result = build_feature_frame(_bars())
    assert result["atr"].iloc[-1] > 0
    assert result["market_sma_200"].iloc[-1] > 0


def test_replay_enters_after_signal_bar() -> None:
    config = Phase10Config(signal_stride=10)
    features = build_feature_frame(_bars())
    replay = replay_symbol(
        features,
        "stock",
        config.stock_profile,
        config.warmup_bars,
        config.signal_stride,
        config.same_bar_policy,
        True,
    )
    assert not replay.empty
    entry = pd.to_datetime(replay["entry_timestamp"])
    signal = pd.to_datetime(replay["signal_timestamp"])
    assert (entry > signal).all()
    assert set(replay["holding_period"]) == set(config.stock_profile.holding_periods)


def test_score_band_assignment() -> None:
    scores = pd.Series([49.0, 60.0, 76.0])
    bands = assign_score_band(scores, (0.0, 50.0, 60.0, 75.0, 101.0))
    assert bands.astype(str).tolist() == ["0-50", "60-75", "75-101"]


def test_aggregate_reports_core_metrics() -> None:
    frame = pd.DataFrame(
        {
            "asset_class": ["stock", "stock"],
            "holding_period": [5, 5],
            "net_return": [0.02, -0.01],
            "mfe": [0.03, 0.01],
            "mae": [-0.01, -0.02],
            "exit_reason": ["target", "stop"],
            "bars_held": [3, 2],
        }
    )
    result = aggregate(frame, ["asset_class", "holding_period"])
    assert int(result.iloc[0]["trades"]) == 2
    assert float(result.iloc[0]["win_rate"]) == 0.5


def test_invalid_phase10_configuration(tmp_path: Path) -> None:
    try:
        Phase10Config(warmup_bars=100, output_root=tmp_path)
    except ValueError as exc:
        assert "warmup_bars" in str(exc)
    else:
        raise AssertionError("Expected invalid configuration to fail")
