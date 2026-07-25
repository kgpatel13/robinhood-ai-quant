from __future__ import annotations

import pandas as pd

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
