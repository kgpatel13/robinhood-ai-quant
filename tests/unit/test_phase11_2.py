from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.research.phase11.label_analysis import (
    class_balance,
    horizon_quality_index,
    label_noise,
    label_overlap,
    label_summary,
    leakage_checks,
)


def _frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in ("AAA", "BBB"):
        for index in range(20):
            for horizon in (1, 3):
                net = 0.01 if index % 2 == 0 else -0.008
                rows.append(
                    {
                        "timestamp": pd.Timestamp("2025-01-01") + pd.Timedelta(days=index),
                        "entry_timestamp": pd.Timestamp("2025-01-02") + pd.Timedelta(days=index),
                        "exit_timestamp": pd.Timestamp("2025-01-02")
                        + pd.Timedelta(days=index + horizon - 1),
                        "symbol": symbol,
                        "asset_class": "stock",
                        "regime": "bull" if index < 10 else "bear",
                        "holding_period": horizon,
                        "forward_return": net + 0.0018,
                        "net_forward_return": net,
                        "mfe": max(net, 0.015),
                        "mae": min(net, -0.01),
                        "positive_return_label": int(net > 0.0),
                        "risk_adjusted_label": net - 0.005,
                    }
                )
    return pd.DataFrame(rows)


def test_label_summary_and_balance() -> None:
    frame = _frame()
    summary = label_summary(frame)
    balance = class_balance(frame)
    assert summary["holding_period"].tolist() == [1, 3]
    assert balance["positive_rate"].tolist() == [0.5, 0.5]


def test_noise_and_overlap() -> None:
    frame = _frame()
    noise = label_noise(frame, 0.25)
    overlap = label_overlap(frame)
    assert noise["binary_label_mismatch_fraction"].max() == 0.0
    assert overlap.iloc[0]["agreement_rate"] == 1.0


def test_leakage_checks_pass() -> None:
    checks = leakage_checks(_frame())
    assert bool(checks["passed"].all())


def test_quality_index_is_bounded() -> None:
    frame = _frame()
    summary = label_summary(frame)
    noise = label_noise(frame, 0.25)
    asset = (
        frame.groupby(["holding_period", "asset_class"])
        .agg(
            rows=("symbol", "size"),
            positive_rate=("positive_return_label", "mean"),
            mean_net_return=("net_forward_return", "mean"),
            median_net_return=("net_forward_return", "median"),
            net_return_std=("net_forward_return", "std"),
        )
        .reset_index()
    )
    regime = (
        frame.groupby(["holding_period", "regime"])
        .agg(
            rows=("symbol", "size"),
            positive_rate=("positive_return_label", "mean"),
            mean_net_return=("net_forward_return", "mean"),
            median_net_return=("net_forward_return", "median"),
            net_return_std=("net_forward_return", "std"),
        )
        .reset_index()
    )
    quality = horizon_quality_index(summary, noise, asset, regime, 10)
    assert quality["label_quality_index"].between(0.0, 1.0).all()


def test_complete_event_sampling_preserves_all_horizons() -> None:
    from src.research.phase11.label_analysis import deterministic_label_sample

    frame = _frame()
    sample = deterministic_label_sample(frame, maximum_rows=20, seed=7)
    horizon_counts = sample.groupby(["timestamp", "symbol"])["holding_period"].nunique()
    assert len(sample) <= 20
    assert (horizon_counts == 2).all()


def test_negative_mean_does_not_receive_directional_signal_credit() -> None:
    frame = _frame()
    frame["net_forward_return"] = -frame["net_forward_return"].abs()
    summary = label_summary(frame)
    noise = label_noise(frame, 0.25)
    asset = (
        frame.groupby(["holding_period", "asset_class"])
        .agg(
            rows=("symbol", "size"),
            positive_rate=("positive_return_label", "mean"),
            mean_net_return=("net_forward_return", "mean"),
            median_net_return=("net_forward_return", "median"),
            net_return_std=("net_forward_return", "std"),
        )
        .reset_index()
    )
    regime = (
        frame.groupby(["holding_period", "regime"])
        .agg(
            rows=("symbol", "size"),
            positive_rate=("positive_return_label", "mean"),
            mean_net_return=("net_forward_return", "mean"),
            median_net_return=("net_forward_return", "median"),
            net_return_std=("net_forward_return", "std"),
        )
        .reset_index()
    )
    quality = horizon_quality_index(summary, noise, asset, regime, 10)
    assert quality["signal_to_noise_score"].max() == 0.0


def test_configured_guardrails_change_horizon_signoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.research.phase11.label_engine import run_label_intelligence
    from src.research.phase11.label_models import LabelIntelligenceConfig

    root = tmp_path
    dataset_path = root / "labels.parquet"
    expanded = pd.concat([_frame(), _frame(), _frame()], ignore_index=True)
    monkeypatch.setattr(pd, "read_parquet", lambda _: expanded)
    result = run_label_intelligence(
        LabelIntelligenceConfig(
            dataset_path=dataset_path,
            output_root=root / "reports",
            maximum_analysis_rows=10_000,
            minimum_horizon_rows=100,
            minimum_positive_rate=0.60,
            maximum_positive_rate=0.80,
            maximum_extreme_return_fraction=1.0,
            minimum_quality_index=0.0,
            secondary_quality_index=0.0,
            primary_quality_index=0.0,
        )
    )
    quality = pd.read_csv(root / "reports" / "horizon_quality.csv")
    assert result.approved_horizons == 0
    assert result.review_horizons == 2
    assert not quality["positive_rate_passed"].any()
    assert (quality["recommendation"] == "REVIEW").all()


def test_extreme_returns_are_diagnostic_not_a_rejection_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.research.phase11.label_engine import run_label_intelligence
    from src.research.phase11.label_models import LabelIntelligenceConfig

    expanded = pd.concat([_frame(), _frame(), _frame()], ignore_index=True)
    expanded["net_forward_return"] = expanded["net_forward_return"].apply(
        lambda value: 0.50 if value > 0.0 else -0.50
    )
    expanded["forward_return"] = expanded["net_forward_return"] + 0.0018
    expanded["positive_return_label"] = (expanded["net_forward_return"] > 0.0).astype(int)
    monkeypatch.setattr(pd, "read_parquet", lambda _: expanded)

    output_root = tmp_path / "reports"
    result = run_label_intelligence(
        LabelIntelligenceConfig(
            dataset_path=tmp_path / "labels.parquet",
            output_root=output_root,
            maximum_analysis_rows=10_000,
            minimum_horizon_rows=100,
            minimum_positive_rate=0.20,
            maximum_positive_rate=0.80,
            maximum_extreme_return_fraction=0.0,
            minimum_quality_index=0.0,
            secondary_quality_index=0.0,
            primary_quality_index=0.0,
        )
    )
    quality = pd.read_csv(output_root / "horizon_quality.csv")
    assert not quality["extreme_return_passed"].any()
    assert quality["guardrails_passed"].all()
    assert (quality["recommendation"] == "PRIMARY").all()
    assert result.approved_horizons == 2
