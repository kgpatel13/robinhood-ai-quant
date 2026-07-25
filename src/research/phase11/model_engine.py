from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.research.phase11.model_analysis import (
    TARGET_COLUMN,
    build_pipeline,
    calibration_table,
    chronological_sample,
    classification_metrics,
    feature_importance_table,
    model_catalog,
    predictor_columns,
    purged_temporal_split,
    subgroup_metrics,
    threshold_economics,
)
from src.research.phase11.model_models import ModelIntelligenceConfig, ModelIntelligenceResult

VERSION = "0.11.10"
PHASE = "11.9"


def run_model_intelligence(config: ModelIntelligenceConfig) -> ModelIntelligenceResult:
    config.output_root.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(config.dataset_path)
    approved_horizons = _approved_horizons(config.label_signoff_path, frame)
    all_metrics: list[dict[str, object]] = []
    all_thresholds: list[pd.DataFrame] = []
    all_splits: list[pd.DataFrame] = []
    all_calibration: list[pd.DataFrame] = []
    all_asset_metrics: list[pd.DataFrame] = []
    all_regime_metrics: list[pd.DataFrame] = []
    all_importance: list[pd.DataFrame] = []
    champion_rows: list[dict[str, object]] = []
    trained_models = 0

    model_root = config.output_root / "models"
    model_root.mkdir(exist_ok=True)

    for horizon in approved_horizons:
        horizon_frame = chronological_sample(
            frame.loc[frame["holding_period"] == horizon].copy(),
            config.maximum_rows_per_horizon,
        )
        split = purged_temporal_split(
            horizon_frame,
            config.train_fraction,
            config.validation_fraction,
            config.purge_bars,
            config.embargo_bars,
        )
        if len(split.train) < config.minimum_train_rows:
            raise ValueError(f"horizon {horizon} has insufficient training rows")
        split_audit = split.audit.copy()
        split_audit.insert(0, "holding_period", horizon)
        all_splits.append(split_audit)

        validation_candidates: list[dict[str, Any]] = []
        fitted: dict[str, Any] = {}
        for model_name, classifier in model_catalog(config.random_seed).items():
            pipeline = build_pipeline(classifier)
            pipeline.fit(split.train[predictor_columns()], split.train[TARGET_COLUMN])
            fitted[model_name] = pipeline
            trained_models += 1
            for partition_name, partition in (
                ("validation", split.validation),
                ("test", split.test),
            ):
                probabilities = pipeline.predict_proba(partition[predictor_columns()])[:, 1]
                partition_metrics = classification_metrics(
                    partition[TARGET_COLUMN], probabilities, 0.50
                )
                all_metrics.append(
                    {
                        "holding_period": horizon,
                        "model": model_name,
                        "partition": partition_name,
                        "rows": len(partition),
                        **partition_metrics,
                    }
                )
                if partition_name == "validation":
                    economics = threshold_economics(
                        partition, probabilities, config.probability_thresholds
                    )
                    economics.insert(0, "model", model_name)
                    economics.insert(0, "holding_period", horizon)
                    economics.insert(2, "partition", "validation")
                    all_thresholds.append(economics)
                    best = _select_threshold(economics)
                    validation_candidates.append(
                        {
                            "model": model_name,
                            "threshold": float(best["threshold"]),
                            "validation_score": _validation_score(partition_metrics, best),
                        }
                    )

        champion = max(validation_candidates, key=lambda row: float(row["validation_score"]))
        champion_name = str(champion["model"])
        threshold = float(champion["threshold"])
        champion_pipeline = fitted[champion_name]
        test_probabilities = champion_pipeline.predict_proba(split.test[predictor_columns()])[:, 1]
        test_metrics = classification_metrics(
            split.test[TARGET_COLUMN], test_probabilities, threshold
        )
        test_economics = threshold_economics(split.test, test_probabilities, (threshold,)).iloc[0]
        passed = (
            test_metrics["roc_auc"] >= config.minimum_test_auc
            and test_metrics["brier_improvement"] >= config.minimum_test_brier_improvement
            and int(test_economics["trades"]) >= config.minimum_test_trades
            and float(test_economics["maximum_drawdown"]) <= config.maximum_test_drawdown
        )
        model_path = model_root / f"horizon_{horizon}_{champion_name}.joblib"
        joblib.dump(champion_pipeline, model_path)
        champion_rows.append(
            {
                "holding_period": horizon,
                "champion_model": champion_name,
                "probability_threshold": threshold,
                "validation_score": champion["validation_score"],
                **{f"test_{key}": value for key, value in test_metrics.items()},
                **{f"test_{key}": value for key, value in test_economics.to_dict().items()},
                "phase12_candidate": bool(passed),
                "model_path": str(model_path),
            }
        )

        calibration = calibration_table(split.test[TARGET_COLUMN], test_probabilities)
        calibration.insert(0, "holding_period", horizon)
        calibration.insert(1, "model", champion_name)
        all_calibration.append(calibration)
        asset = subgroup_metrics(split.test, test_probabilities, threshold, "asset_class")
        asset.insert(0, "holding_period", horizon)
        asset.insert(1, "model", champion_name)
        all_asset_metrics.append(asset)
        regime = subgroup_metrics(split.test, test_probabilities, threshold, "regime")
        regime.insert(0, "holding_period", horizon)
        regime.insert(1, "model", champion_name)
        all_regime_metrics.append(regime)
        importance = feature_importance_table(champion_pipeline)
        importance.insert(0, "holding_period", horizon)
        importance.insert(1, "model", champion_name)
        all_importance.append(importance)

    metrics = pd.DataFrame(all_metrics)
    thresholds = pd.concat(all_thresholds, ignore_index=True)
    splits = pd.concat(all_splits, ignore_index=True)
    calibration = pd.concat(all_calibration, ignore_index=True)
    asset_metrics = pd.concat(all_asset_metrics, ignore_index=True)
    regime_metrics = pd.concat(all_regime_metrics, ignore_index=True)
    importance = pd.concat(all_importance, ignore_index=True)
    champions = pd.DataFrame(champion_rows).sort_values("holding_period", kind="stable")

    artifacts = _write_artifacts(
        config,
        metrics,
        thresholds,
        splits,
        calibration,
        asset_metrics,
        regime_metrics,
        importance,
        champions,
        len(frame),
    )
    diagnostics_passed = bool(splits["chronology_passed"].all())
    approved = diagnostics_passed and bool(champions["phase12_candidate"].any())
    return ModelIntelligenceResult(
        rows_analyzed=int(sum(splits["rows"])),
        horizons_analyzed=len(approved_horizons),
        models_trained=trained_models,
        champions_selected=len(champions),
        diagnostics_passed=diagnostics_passed,
        approved_for_phase12_review=approved,
        output=str(config.output_root),
        artifacts=artifacts,
    )


def _approved_horizons(path: Path, frame: pd.DataFrame) -> list[int]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = [int(value) for value in payload.get("approved_horizons", [])]
        if values:
            return values
    return sorted(int(value) for value in frame["holding_period"].unique())


def _select_threshold(economics: pd.DataFrame) -> pd.Series:
    eligible = economics.loc[economics["trades"] > 0].copy()
    if eligible.empty:
        return economics.iloc[0]
    eligible["selection_score"] = (
        eligible["mean_net_return"].clip(lower=-1.0, upper=1.0)
        + 0.10 * eligible["win_rate"]
        - 0.20 * eligible["maximum_drawdown"]
    )
    return eligible.sort_values(
        ["selection_score", "trades"], ascending=[False, False], kind="stable"
    ).iloc[0]


def _validation_score(metrics: dict[str, float], economics: pd.Series) -> float:
    return float(
        0.35 * metrics["roc_auc"]
        + 0.20 * metrics["average_precision"]
        + 0.15 * metrics["balanced_accuracy"]
        + 0.20 * np.tanh(float(economics["mean_net_return"]) * 100.0)
        - 0.10 * float(economics["maximum_drawdown"])
    )


def _write_artifacts(
    config: ModelIntelligenceConfig,
    metrics: pd.DataFrame,
    thresholds: pd.DataFrame,
    splits: pd.DataFrame,
    calibration: pd.DataFrame,
    asset_metrics: pd.DataFrame,
    regime_metrics: pd.DataFrame,
    importance: pd.DataFrame,
    champions: pd.DataFrame,
    dataset_rows: int,
) -> dict[str, str]:
    files = {
        "split_audit": "temporal_split_audit.csv",
        "baseline_metrics": "baseline_model_metrics.csv",
        "threshold_analysis": "threshold_analysis.csv",
        "calibration": "probability_calibration.csv",
        "asset_robustness": "asset_model_robustness.csv",
        "regime_robustness": "regime_model_robustness.csv",
        "feature_importance": "champion_feature_importance.csv",
        "champions": "champion_models.csv",
        "dashboard": "phase11_model_dashboard.json",
        "signoff": "phase11_final_signoff.json",
        "manifest": "manifest.json",
    }
    tables = {
        "split_audit": splits,
        "baseline_metrics": metrics,
        "threshold_analysis": thresholds,
        "calibration": calibration,
        "asset_robustness": asset_metrics,
        "regime_robustness": regime_metrics,
        "feature_importance": importance,
        "champions": champions,
    }
    for key, table in tables.items():
        table.to_csv(config.output_root / files[key], index=False)

    diagnostics_passed = bool(splits["chronology_passed"].all())
    candidate_count = int(champions["phase12_candidate"].sum())
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "dataset": str(config.dataset_path),
        "dataset_rows": dataset_rows,
        "horizons_analyzed": len(champions),
        "models_trained": int(len(metrics) // 2),
        "champions_selected": len(champions),
        "phase12_candidates": candidate_count,
        "diagnostics_passed": diagnostics_passed,
    }
    signoff = {
        "phase": PHASE,
        "status": "PHASE11_RESEARCH_COMPLETE",
        "diagnostics_passed": diagnostics_passed,
        "approved_for_phase12_review": diagnostics_passed and candidate_count > 0,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "candidate_horizons": champions.loc[champions["phase12_candidate"], "holding_period"]
        .astype(int)
        .tolist(),
        "blocked_horizons": champions.loc[~champions["phase12_candidate"], "holding_period"]
        .astype(int)
        .tolist(),
        "notes": [
            "Chronological train/validation/test partitions include purge and embargo gaps.",
            (
                "Model and threshold selection use validation data only; "
                "test data is reserved for final reporting."
            ),
            (
                "Phase 12 review is research approval only and does not authorize "
                "paper or live trading."
            ),
        ],
    }
    manifest = {
        "phase": PHASE,
        "version": VERSION,
        "artifacts": {key: str(config.output_root / value) for key, value in files.items()},
    }
    (config.output_root / files["dashboard"]).write_text(
        json.dumps(dashboard, indent=2), encoding="utf-8"
    )
    (config.output_root / files["signoff"]).write_text(
        json.dumps(signoff, indent=2), encoding="utf-8"
    )
    (config.output_root / files["manifest"]).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {key: str(config.output_root / value) for key, value in files.items()}
