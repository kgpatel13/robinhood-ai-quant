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


def test_portfolio_simulation_blocks_overlapping_symbol_positions() -> None:
    from src.research.phase10.portfolio import PortfolioConfig, simulate_portfolio

    timestamps = pd.to_datetime(["2025-01-02", "2025-01-03"], utc=True)
    signals = pd.DataFrame(
        {
            "symbol": ["TEST", "TEST"],
            "asset_class": ["stock", "stock"],
            "holding_period": [5, 5],
            "entry_timestamp": timestamps,
            "exit_timestamp": pd.to_datetime(["2025-01-06", "2025-01-07"], utc=True),
            "entry_price": [100.0, 101.0],
            "exit_price": [105.0, 106.0],
            "stop_price": [95.0, 96.0],
            "opportunity_score": [80.0, 81.0],
        }
    )
    prices = pd.DataFrame(
        {"TEST": [100.0, 101.0, 102.0, 103.0, 105.0, 106.0]},
        index=pd.date_range("2025-01-02", periods=6, freq="D", tz="UTC"),
    )
    trades, equity, summary, skipped = simulate_portfolio(
        signals,
        prices,
        PortfolioConfig(maximum_concurrent_positions=2),
        {"asset_class": "stock", "holding_period": 5, "threshold": 62.0},
    )
    assert len(trades) == 1
    assert not equity.empty
    assert int(summary["skipped_signals"]) == 1
    assert skipped.iloc[0]["skip_reason"] == "position_already_open"


def test_walk_forward_uses_train_selected_threshold() -> None:
    from src.research.phase10.walk_forward import fixed_split_validation

    replay = pd.DataFrame(
        {
            "asset_class": ["stock"] * 8,
            "holding_period": [5] * 8,
            "signal_timestamp": pd.to_datetime(
                [
                    "2021-01-01",
                    "2021-02-01",
                    "2022-01-01",
                    "2022-02-01",
                    "2023-01-01",
                    "2024-01-01",
                    "2025-01-01",
                    "2026-01-01",
                ],
                utc=True,
            ),
            "opportunity_score": [75, 76, 80, 81, 79, 82, 80, 83],
            "net_return": [0.02, 0.01, 0.03, 0.02, 0.01, -0.01, 0.02, 0.01],
        }
    )
    result = fixed_split_validation(
        replay,
        {"stock": (62.0, 75.0), "etf": (62.0,), "crypto": (64.0,)},
        2022,
        2024,
        {"stock": 2, "etf": 2, "crypto": 2},
    )
    assert set(result["split"]) == {"train", "validation", "test"}
    assert result["selected_threshold"].notna().all()


def test_rolling_walk_forward_uses_only_prior_windows() -> None:
    from src.research.phase10.robustness import rolling_walk_forward_validation

    rows: list[dict[str, object]] = []
    for year in range(2015, 2026):
        for score, result in ((70.0, 0.01), (80.0, 0.02)):
            rows.append(
                {
                    "asset_class": "stock",
                    "holding_period": 10,
                    "signal_timestamp": pd.Timestamp(f"{year}-06-01", tz="UTC"),
                    "opportunity_score": score,
                    "net_return": result if year < 2025 else -0.01,
                }
            )
    result = rolling_walk_forward_validation(
        pd.DataFrame(rows),
        {"stock": (70.0, 80.0)},
        {"stock": 2},
        train_years=5,
        validation_years=1,
        test_years=1,
    )
    assert not result.empty
    assert (result["test_start_year"] > result["validation_end_year"]).all()
    assert (result["validation_start_year"] > result["train_end_year"]).all()


def test_leakage_audit_detects_bad_timestamp() -> None:
    from src.research.phase10.robustness import leakage_audit

    replay = pd.DataFrame(
        {
            "signal_timestamp": pd.to_datetime(["2025-01-02"], utc=True),
            "entry_timestamp": pd.to_datetime(["2025-01-01"], utc=True),
            "exit_timestamp": pd.to_datetime(["2025-01-03"], utc=True),
            "entry_price": [100.0],
            "exit_price": [101.0],
            "stop_price": [95.0],
            "target_price": [105.0],
            "opportunity_score": [80.0],
            "net_return": [0.01],
        }
    )
    result = leakage_audit(replay)
    check = result[result["check"] == "entry_after_signal"].iloc[0]
    assert not bool(check["passed"])
    assert int(check["violations"]) == 1


def test_advanced_validation_outputs_are_deterministic() -> None:
    from src.research.phase10.advanced_validation import (
        bootstrap_confidence,
        cross_sectional_rank_analysis,
        label_quality_analysis,
        time_decay_analysis,
    )

    replay = pd.DataFrame(
        {
            "asset_class": ["stock"] * 8,
            "holding_period": [5] * 8,
            "eligible": [True] * 8,
            "signal_timestamp": pd.to_datetime(["2023-01-01"] * 4 + ["2025-01-01"] * 4, utc=True),
            "opportunity_score": [60, 70, 80, 90, 60, 70, 80, 90],
            "net_return": [-0.02, -0.01, 0.01, 0.03, -0.01, 0.00, 0.02, 0.04],
            "mfe": [0.01, 0.01, 0.02, 0.04, 0.01, 0.01, 0.03, 0.05],
            "mae": [-0.03, -0.02, -0.01, -0.01, -0.02, -0.01, -0.01, -0.01],
        }
    )
    assert not label_quality_analysis(replay).empty
    rank = cross_sectional_rank_analysis(replay)
    assert float(rank.sort_values("rank_quantile").iloc[-1]["average_return"]) > float(
        rank.sort_values("rank_quantile").iloc[0]["average_return"]
    )
    assert not time_decay_analysis(replay).empty
    first = bootstrap_confidence(replay, samples=200, seed=10)
    second = bootstrap_confidence(replay, samples=200, seed=10)
    pd.testing.assert_frame_equal(first, second)


def test_replay_contains_point_in_time_features() -> None:
    config = Phase10Config(signal_stride=10)
    replay = replay_symbol(
        build_feature_frame(_bars()),
        "stock",
        config.stock_profile,
        config.warmup_bars,
        config.signal_stride,
        config.same_bar_policy,
        True,
    )
    assert {"momentum_21", "relative_volume", "rsi_14"}.issubset(replay.columns)
