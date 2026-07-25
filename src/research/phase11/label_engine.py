from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase11.label_analysis import (
    LABEL_COLUMNS,
    class_balance,
    deterministic_label_sample,
    grouped_quality,
    horizon_quality_index,
    label_noise,
    label_overlap,
    label_summary,
    leakage_checks,
    return_distribution,
    risk_reward_distribution,
)
from src.research.phase11.label_models import LabelIntelligenceConfig, LabelIntelligenceResult


def _write_json(payload: object, path: Path) -> str:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def run_label_intelligence(config: LabelIntelligenceConfig) -> LabelIntelligenceResult:
    config.output_root.mkdir(parents=True, exist_ok=True)
    dataset = pd.read_parquet(config.dataset_path)
    required = {
        "timestamp",
        "entry_timestamp",
        "exit_timestamp",
        "symbol",
        "asset_class",
        "regime",
        "holding_period",
        *LABEL_COLUMNS,
    }
    missing = sorted(required - set(dataset.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    sample = deterministic_label_sample(dataset, config.maximum_analysis_rows, config.random_seed)
    summary = label_summary(sample)
    balance = class_balance(sample)
    returns = return_distribution(sample)
    risk_reward = risk_reward_distribution(sample)
    noise = label_noise(sample, config.extreme_return_threshold)
    overlap = label_overlap(sample)
    asset = grouped_quality(sample, "asset_class")
    regime = grouped_quality(sample, "regime")
    quality = horizon_quality_index(summary, noise, asset, regime, config.minimum_horizon_rows)
    quality["recommendation"] = quality["label_quality_index"].map(
        lambda value: "APPROVE" if value >= config.minimum_quality_index else "REVIEW"
    )
    leakage = leakage_checks(sample)
    diagnostics_passed = bool(leakage["passed"].all()) and bool(
        (summary["rows"] >= config.minimum_horizon_rows).all()
    )
    reports = {
        "label_summary": summary,
        "horizon_quality": quality,
        "class_balance": balance,
        "return_distribution": returns,
        "risk_reward_distribution": risk_reward,
        "label_noise": noise,
        "label_overlap": overlap,
        "horizon_comparison": quality,
        "regime_label_quality": regime,
        "asset_label_quality": asset,
        "leakage_checks": leakage,
    }
    artifacts: dict[str, str] = {}
    for name, frame in reports.items():
        path = config.output_root / f"{name}.csv"
        frame.to_csv(path, index=False)
        artifacts[name] = str(path)
    approved = int((quality["recommendation"] == "APPROVE").sum())
    dashboard = {
        "phase": "11.2.0",
        "version": "0.11.2",
        "dataset": str(config.dataset_path),
        "dataset_rows": len(dataset),
        "rows_analyzed": len(sample),
        "horizons_analyzed": int(summary["holding_period"].nunique()),
        "approved_horizons": approved,
        "review_horizons": int((quality["recommendation"] == "REVIEW").sum()),
        "best_horizon": int(quality.iloc[0]["holding_period"]),
        "diagnostics_passed": diagnostics_passed,
    }
    artifacts["dashboard"] = _write_json(dashboard, config.output_root / "label_dashboard.json")
    manifest = {
        "phase": "11.2.0",
        "version": "0.11.2",
        "purpose": "label intelligence and target validation",
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        **dashboard,
    }
    artifacts["manifest"] = _write_json(manifest, config.output_root / "manifest.json")
    training_approved = diagnostics_passed and approved > 0
    signoff = {
        "phase": "11.2.0",
        "status": "LABEL_INTELLIGENCE_COMPLETE"
        if diagnostics_passed
        else "LABEL_INTELLIGENCE_REVIEW_REQUIRED",
        "diagnostics_passed": diagnostics_passed,
        "approved_for_baseline_models": training_approved,
        "approved_for_model_training": training_approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "approved_horizons": [
            int(value)
            for value in quality.loc[
                quality["recommendation"] == "APPROVE", "holding_period"
            ].tolist()
        ],
        "review_horizons": [
            int(value)
            for value in quality.loc[
                quality["recommendation"] == "REVIEW", "holding_period"
            ].tolist()
        ],
        "notes": [
            "Horizon recommendations are research guidance.",
            "Paper and live trading remain blocked until later validation phases.",
        ],
    }
    artifacts["signoff"] = _write_json(signoff, config.output_root / "phase11_label_signoff.json")
    return LabelIntelligenceResult(
        len(sample),
        int(summary["holding_period"].nunique()),
        approved,
        int((quality["recommendation"] == "REVIEW").sum()),
        str(config.output_root),
        diagnostics_passed,
        artifacts,
    )
