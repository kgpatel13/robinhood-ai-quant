from __future__ import annotations

import csv
import json
from pathlib import Path

from src.atlas.alpha_pipeline import AlphaPipelineConfig, run_alpha_pipeline
from src.atlas.ranking import RankingConfig, RankingEngine


def test_ranking_engine_orders_scores_and_assigns_percentiles() -> None:
    result = RankingEngine(RankingConfig(top_n=2, bottom_n=1)).rank(
        {"a": 0.1, "b": 0.9, "c": 0.5, "d": None},
        {
            "a": {"momentum": -1.0},
            "b": {"momentum": 1.0},
            "c": {"momentum": 0.0},
            "d": {"momentum": None},
        },
        {
            "a": {"symbol": "A", "asset_class": "stock", "timestamp": "2026-01-01"},
            "b": {"symbol": "B", "asset_class": "stock", "timestamp": "2026-01-01"},
            "c": {"symbol": "C", "asset_class": "crypto", "timestamp": "2026-01-01"},
        },
    )
    assert [asset.asset_id for asset in result.ranked_assets] == ["b", "c", "a"]
    assert result.ranked_assets[0].alpha_percentile == 1.0
    assert result.ranked_assets[-1].alpha_percentile == 0.0
    assert [asset.asset_id for asset in result.top_assets] == ["b", "c"]
    assert [asset.asset_id for asset in result.bottom_assets] == ["a"]
    assert result.excluded_assets == ("d",)


def test_alpha_pipeline_generates_reports(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.csv"
    reports = tmp_path / "reports"
    fieldnames = [
        "asset_id",
        "symbol",
        "asset_class",
        "timestamp",
        "return_20d",
        "return_60d",
        "return_120d",
        "return_252d",
        "return_5d",
        "price_to_sma_20",
        "price_to_sma_50",
        "price_to_sma_100",
        "price_to_sma_200",
        "trend_persistence_20",
        "trend_persistence_60",
        "volatility_20d",
        "volatility_60d",
        "volatility_120d",
        "atr_pct_20",
        "bollinger_width_20",
        "average_dollar_volume_20d",
        "average_dollar_volume_60d",
        "relative_volume_20d",
        "money_flow_ratio_20",
        "rsi_14",
        "stochastic_20",
        "bollinger_z_20",
        "distance_from_high_20",
        "bar_count",
        "zero_volume_ratio_60",
        "gap_ratio_60",
    ]
    with feature_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(4):
            value = float(index + 1)
            writer.writerow(
                {
                    name: (
                        f"asset:{index}"
                        if name == "asset_id"
                        else f"S{index}"
                        if name == "symbol"
                        else "stock"
                        if name == "asset_class"
                        else "2026-01-01"
                        if name == "timestamp"
                        else value
                    )
                    for name in fieldnames
                }
            )

    result = run_alpha_pipeline(
        AlphaPipelineConfig(
            feature_store_path=feature_path,
            report_directory=reports,
            top_n=2,
            bottom_n=1,
        )
    )
    assert result.complete
    assert result.input_assets == 4
    assert result.ranked_assets == 4
    assert (reports / "factor_scores.csv").exists()
    assert (reports / "ranked_assets.csv").exists()
    summary = json.loads((reports / "ranking_summary.json").read_text())
    assert summary["factor_count"] == 6
    opportunities = json.loads((reports / "top_opportunities.json").read_text())
    assert len(opportunities["top"]) == 2
    assert len(opportunities["bottom"]) == 1
