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

PHASE = "11.2.2"
VERSION = "0.11.4"


def _write_json(payload: object, path: Path) -> str:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def _recommend_horizon(row: pd.Series, config: LabelIntelligenceConfig) -> str:
    if not bool(row["guardrails_passed"]):
        return "REVIEW"
    quality = float(row["label_quality_index"])
    if quality >= config.primary_quality_index:
        return "PRIMARY"
    if quality >= config.secondary_quality_index:
        return "SECONDARY"
    return "EXPLORATORY"


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
    quality = quality.merge(
        summary[["holding_period", "rows", "positive_rate"]],
        on="holding_period",
        how="left",
        validate="one_to_one",
    ).merge(
        noise[["holding_period", "extreme_return_fraction"]],
        on="holding_period",
        how="left",
        validate="one_to_one",
    )
    quality["minimum_rows_passed"] = quality["rows"] >= config.minimum_horizon_rows
    quality["positive_rate_passed"] = quality["positive_rate"].between(
        config.minimum_positive_rate, config.maximum_positive_rate, inclusive="both"
    )
    quality["extreme_return_passed"] = (
        quality["extreme_return_fraction"] <= config.maximum_extreme_return_fraction
    )
    quality["quality_index_passed"] = quality["label_quality_index"] >= config.minimum_quality_index
    # Extreme-return frequency is horizon-dependent and remains diagnostic only.
    # It must not reject an otherwise valid label horizon by itself.
    quality["guardrails_passed"] = quality[
        [
            "minimum_rows_passed",
            "positive_rate_passed",
            "quality_index_passed",
        ]
    ].all(axis=1)
    quality["recommendation"] = quality.apply(_recommend_horizon, axis=1, config=config)

    leakage = leakage_checks(sample)
    diagnostics_passed = bool(leakage["passed"].all())
    eligible = quality["recommendation"] != "REVIEW"
    approved = int(eligible.sum())
    review = int((~eligible).sum())

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

    priority_counts = {
        name.lower(): int((quality["recommendation"] == name).sum())
        for name in ("PRIMARY", "SECONDARY", "EXPLORATORY", "REVIEW")
    }
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "dataset": str(config.dataset_path),
        "dataset_rows": len(dataset),
        "rows_analyzed": len(sample),
        "horizons_analyzed": int(summary["holding_period"].nunique()),
        "approved_horizons": approved,
        "review_horizons": review,
        "priority_counts": priority_counts,
        "best_horizon": int(quality.iloc[0]["holding_period"]),
        "diagnostics_passed": diagnostics_passed,
    }
    artifacts["dashboard"] = _write_json(dashboard, config.output_root / "label_dashboard.json")
    manifest = {
        "phase": PHASE,
        "version": VERSION,
        "purpose": "hardened label intelligence and target validation",
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        **dashboard,
    }
    artifacts["manifest"] = _write_json(manifest, config.output_root / "manifest.json")

    training_approved = diagnostics_passed and approved > 0
    horizons_by_priority = {
        priority.lower() + "_horizons": [
            int(value)
            for value in quality.loc[
                quality["recommendation"] == priority, "holding_period"
            ].tolist()
        ]
        for priority in ("PRIMARY", "SECONDARY", "EXPLORATORY", "REVIEW")
    }
    signoff = {
        "phase": PHASE,
        "status": "LABEL_INTELLIGENCE_HARDENING_COMPLETE"
        if training_approved
        else "LABEL_INTELLIGENCE_REVIEW_REQUIRED",
        "diagnostics_passed": diagnostics_passed,
        "approved_for_baseline_models": training_approved,
        "approved_for_model_training": training_approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "approved_horizons": [
            int(value) for value in quality.loc[eligible, "holding_period"].tolist()
        ],
        **horizons_by_priority,
        "notes": [
            "Horizon priorities are research guidance, not evidence of model profitability.",
            "Configured class-balance, sample-size, and quality guardrails are "
            "enforced per horizon.",
            "Extreme-return frequency remains a reported diagnostic and does not "
            "independently reject a horizon.",
            "Paper and live trading remain blocked until later validation phases.",
        ],
    }
    artifacts["signoff"] = _write_json(signoff, config.output_root / "phase11_label_signoff.json")
    return LabelIntelligenceResult(
        len(sample),
        int(summary["holding_period"].nunique()),
        approved,
        review,
        str(config.output_root),
        diagnostics_passed,
        artifacts,
    )
