from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase11.intelligence import (
    correlation_matrix,
    coverage_report,
    deterministic_sample,
    feature_drift,
    feature_outliers,
    feature_predictiveness,
    feature_recommendations,
    feature_redundancy,
    feature_stability,
    feature_summary,
    leakage_diagnostics,
)
from src.research.phase11.intelligence_models import (
    FeatureIntelligenceConfig,
    FeatureIntelligenceResult,
)


def _write_json(payload: object, path: Path) -> str:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def run_feature_intelligence(
    config: FeatureIntelligenceConfig,
) -> FeatureIntelligenceResult:
    config.output_root.mkdir(parents=True, exist_ok=True)
    dataset = pd.read_parquet(config.dataset_path)
    required = {
        "timestamp",
        "symbol",
        "asset_class",
        "holding_period",
        "regime",
        config.target_column,
        config.classification_target,
        *FEATURE_COLUMNS,
    }
    missing = sorted(required - set(dataset.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    sample = deterministic_sample(dataset, config.maximum_analysis_rows)
    summary = feature_summary(sample)
    outliers = feature_outliers(sample, config.outlier_z_threshold)
    correlations = correlation_matrix(sample)
    redundancy = feature_redundancy(sample, config.correlation_threshold)
    predictiveness = feature_predictiveness(
        sample,
        config.target_column,
        config.classification_target,
    )
    drift = feature_drift(sample)
    stability = feature_stability(sample, config.target_column)
    coverage = coverage_report(dataset)
    leakage = leakage_diagnostics(
        summary,
        predictiveness,
        config.suspicious_target_correlation,
    )
    recommendations = feature_recommendations(
        summary,
        outliers,
        predictiveness,
        stability,
        drift,
        redundancy,
        config,
    )
    diagnostics_passed = bool(not leakage.empty and leakage["passed"].all())
    artifacts: dict[str, str] = {}
    reports = {
        "feature_summary": summary,
        "feature_outliers": outliers,
        "feature_correlations": correlations,
        "feature_redundancy": redundancy,
        "feature_predictiveness": predictiveness,
        "feature_drift": drift,
        "feature_stability": stability,
        "coverage_report": coverage,
        "leakage_diagnostics": leakage,
        "feature_recommendations": recommendations,
    }
    for name, frame in reports.items():
        path = config.output_root / f"{name}.csv"
        frame.to_csv(path, index=False)
        artifacts[name] = str(path)

    counts = recommendations["recommendation"].value_counts().to_dict()
    dashboard = {
        "phase": "11.1.0",
        "version": "0.11.1",
        "dataset": str(config.dataset_path),
        "dataset_rows": len(dataset),
        "rows_analyzed": len(sample),
        "total_features": len(FEATURE_COLUMNS),
        "recommendation_counts": {str(key): int(value) for key, value in counts.items()},
        "redundant_pairs": len(redundancy),
        "drifting_features": (
            int(drift.loc[drift["drift_score"] >= config.drift_threshold, "feature"].nunique())
            if not drift.empty
            else 0
        ),
        "diagnostics_passed": diagnostics_passed,
    }
    artifacts["dashboard"] = _write_json(
        dashboard,
        config.output_root / "feature_dashboard.json",
    )
    manifest = {
        "phase": "11.1.0",
        "version": "0.11.1",
        "purpose": "feature intelligence and dataset diagnostics",
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        **dashboard,
    }
    artifacts["manifest"] = _write_json(manifest, config.output_root / "manifest.json")
    signoff = {
        "phase": "11.1.0",
        "status": (
            "FEATURE_INTELLIGENCE_COMPLETE"
            if diagnostics_passed
            else "FEATURE_INTELLIGENCE_REVIEW_REQUIRED"
        ),
        "diagnostics_passed": diagnostics_passed,
        "approved_for_label_validation": diagnostics_passed,
        "approved_for_model_training": False,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "notes": [
            "Recommendations are research guidance, not automated feature deletion.",
            "Model training remains blocked until Phase 11.2 label intelligence is complete.",
        ],
    }
    artifacts["signoff"] = _write_json(
        signoff,
        config.output_root / "phase11_feature_signoff.json",
    )
    return FeatureIntelligenceResult(
        rows_analyzed=len(sample),
        total_features=len(FEATURE_COLUMNS),
        recommended_keep=int(recommendations["recommendation"].str.startswith("KEEP").sum()),
        recommended_review=int((recommendations["recommendation"] == "REVIEW").sum()),
        recommended_remove=int((recommendations["recommendation"] == "REMOVE").sum()),
        output=str(config.output_root),
        diagnostics_passed=diagnostics_passed,
        artifacts=artifacts,
    )
