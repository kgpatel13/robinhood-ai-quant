from __future__ import annotations

import json

import pandas as pd
from sklearn.pipeline import Pipeline

from src.research.phase12.analysis import (
    TARGET_COLUMN,
    PlattCalibrator,
    build_pipeline,
    chronological_sample,
    expanding_walk_forward_folds,
    feature_sets,
    fit_platt_calibrator,
    model_catalog,
    probability_metrics,
    realistic_portfolio_simulation,
)
from src.research.phase12.models import Phase12Config, Phase12Result

PHASE = "12.0-12.9"
VERSION = "0.12.0"


def run_phase12(config: Phase12Config) -> Phase12Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(config.dataset_path)
    required = {
        "timestamp",
        "symbol",
        "holding_period",
        "positive_return_label",
        "net_forward_return",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"dataset is missing required columns: {missing}")

    audit_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    threshold_rows: list[dict[str, object]] = []
    trade_frames: list[pd.DataFrame] = []
    models_trained = 0
    folds_completed = 0

    available_horizons = set(frame["holding_period"].astype(int).unique())
    horizons = [value for value in config.horizons if value in available_horizons]
    if not horizons:
        raise ValueError("none of the configured horizons exist in the dataset")

    for horizon in horizons:
        horizon_frame = frame.loc[frame["holding_period"].astype(int) == horizon].copy()
        horizon_frame = chronological_sample(horizon_frame, config.maximum_rows_per_horizon)
        folds = expanding_walk_forward_folds(
            horizon_frame,
            config.folds,
            config.minimum_train_timestamps,
            config.calibration_fraction,
            config.test_fraction,
            config.purge_bars,
            config.embargo_bars,
        )
        for fold in folds:
            folds_completed += 1
            audit_rows.append({"holding_period": horizon, **fold.audit})
            candidates: list[dict[str, object]] = []
            fitted: dict[tuple[str, str], tuple[Pipeline, PlattCalibrator, tuple[str, ...]]] = {}
            for feature_set_name, columns in feature_sets().items():
                for model_name, model in model_catalog(config.random_seed + fold.fold).items():
                    pipeline = build_pipeline(model, columns)
                    pipeline.fit(fold.train.loc[:, list(columns)], fold.train[TARGET_COLUMN])
                    raw_calibration = pipeline.predict_proba(
                        fold.calibration.loc[:, list(columns)]
                    )[:, 1]
                    calibrator = fit_platt_calibrator(
                        raw_calibration, fold.calibration[TARGET_COLUMN]
                    )
                    calibrated = calibrator.transform(raw_calibration)
                    calibration_metrics = probability_metrics(
                        fold.calibration[TARGET_COLUMN], calibrated
                    )
                    score = (
                        calibration_metrics["roc_auc"]
                        + 2.0 * calibration_metrics["brier_improvement"]
                    )
                    candidates.append(
                        {
                            "feature_set": feature_set_name,
                            "model": model_name,
                            "selection_score": score,
                            **{
                                f"calibration_{key}": value
                                for key, value in calibration_metrics.items()
                            },
                        }
                    )
                    fitted[(feature_set_name, model_name)] = (pipeline, calibrator, columns)
                    models_trained += 1

            champion = max(
                candidates,
                key=lambda item: float(str(item["selection_score"])),
            )
            champion_key = (str(champion["feature_set"]), str(champion["model"]))
            pipeline, calibrator, columns = fitted[champion_key]
            test_probabilities = calibrator.transform(
                pipeline.predict_proba(fold.test.loc[:, list(columns)])[:, 1]
            )
            test_metrics = probability_metrics(fold.test[TARGET_COLUMN], test_probabilities)
            metric_rows.append(
                {
                    "holding_period": horizon,
                    "fold": fold.fold,
                    "feature_set": champion["feature_set"],
                    "model": champion["model"],
                    **champion,
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                }
            )

            calibration_economics: list[dict[str, float | int]] = []
            champion_pipeline, champion_calibrator, champion_columns = fitted[champion_key]
            calibration_probabilities = champion_calibrator.transform(
                champion_pipeline.predict_proba(fold.calibration.loc[:, list(champion_columns)])[
                    :, 1
                ]
            )
            for threshold in config.probability_thresholds:
                calibration_result, _ = realistic_portfolio_simulation(
                    fold.calibration,
                    calibration_probabilities,
                    threshold,
                    horizon,
                    config.initial_capital,
                    config.maximum_open_positions,
                    config.allocation_per_trade,
                    config.slippage_bps,
                    config.commission_bps,
                )
                calibration_economics.append(calibration_result)
            eligible_economics = [item for item in calibration_economics if int(item["trades"]) > 0]
            selection_pool = eligible_economics or calibration_economics
            selected = max(
                selection_pool,
                key=lambda item: (
                    float(item["return_to_drawdown"]),
                    int(item["trades"]),
                ),
            )
            threshold = float(selected["threshold"])
            test_economics, trades = realistic_portfolio_simulation(
                fold.test,
                test_probabilities,
                threshold,
                horizon,
                config.initial_capital,
                config.maximum_open_positions,
                config.allocation_per_trade,
                config.slippage_bps,
                config.commission_bps,
            )
            threshold_rows.append(
                {
                    "holding_period": horizon,
                    "fold": fold.fold,
                    "feature_set": champion["feature_set"],
                    "model": champion["model"],
                    "selected_threshold": threshold,
                    **{f"test_{key}": value for key, value in test_economics.items()},
                }
            )
            if not trades.empty:
                trades.insert(0, "holding_period", horizon)
                trades.insert(1, "fold", fold.fold)
                trade_frames.append(trades)

    audits = pd.DataFrame(audit_rows)
    metrics = pd.DataFrame(metric_rows)
    economics_frame = pd.DataFrame(threshold_rows)
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    horizon_summary = _horizon_summary(metrics, economics_frame, config)
    diagnostics_passed = bool(audits["chronology_passed"].all())
    approved = diagnostics_passed and bool(horizon_summary["paper_trading_candidate"].any())
    artifacts = _write_artifacts(
        config,
        audits,
        metrics,
        economics_frame,
        trades,
        horizon_summary,
        len(frame),
        diagnostics_passed,
        approved,
    )
    return Phase12Result(
        rows_analyzed=int(
            sum(audits["train_rows"] + audits["calibration_rows"] + audits["test_rows"])
        ),
        horizons_analyzed=len(horizons),
        folds_completed=folds_completed,
        models_trained=models_trained,
        diagnostics_passed=diagnostics_passed,
        approved_for_paper_trading_review=approved,
        output=str(config.output_root),
        artifacts=artifacts,
    )


def _horizon_summary(
    metrics: pd.DataFrame, economics: pd.DataFrame, config: Phase12Config
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for horizon, group in metrics.groupby("holding_period", sort=True):
        economic_group = economics.loc[economics["holding_period"] == horizon]
        profitable_fraction = float((economic_group["test_total_return"] > 0.0).mean())
        total_trades = int(economic_group["test_trades"].sum())
        maximum_drawdown = float(economic_group["test_maximum_drawdown"].max())
        minimum_auc = float(group["test_roc_auc"].min())
        median_auc = float(group["test_roc_auc"].median())
        candidate = (
            minimum_auc >= config.minimum_fold_auc
            and median_auc >= config.minimum_median_auc
            and profitable_fraction >= config.minimum_profitable_folds
            and total_trades >= config.minimum_total_trades
            and maximum_drawdown <= config.maximum_drawdown
        )
        rows.append(
            {
                "holding_period": int(str(horizon)),
                "folds": len(group),
                "minimum_test_auc": minimum_auc,
                "median_test_auc": median_auc,
                "mean_test_auc": float(group["test_roc_auc"].mean()),
                "mean_brier_improvement": float(group["test_brier_improvement"].mean()),
                "profitable_fold_fraction": profitable_fraction,
                "total_trades": total_trades,
                "mean_total_return": float(economic_group["test_total_return"].mean()),
                "worst_maximum_drawdown": maximum_drawdown,
                "paper_trading_candidate": bool(candidate),
            }
        )
    return pd.DataFrame(rows)


def _write_artifacts(
    config: Phase12Config,
    audits: pd.DataFrame,
    metrics: pd.DataFrame,
    economics: pd.DataFrame,
    trades: pd.DataFrame,
    summary: pd.DataFrame,
    dataset_rows: int,
    diagnostics_passed: bool,
    approved: bool,
) -> dict[str, str]:
    files = {
        "walk_forward_audit": "walk_forward_audit.csv",
        "fold_metrics": "walk_forward_model_metrics.csv",
        "economic_validation": "economic_validation.csv",
        "simulated_trades": "simulated_trades.csv",
        "horizon_summary": "horizon_summary.csv",
        "dashboard": "phase12_dashboard.json",
        "signoff": "phase12_final_signoff.json",
        "manifest": "manifest.json",
    }
    tables = {
        "walk_forward_audit": audits,
        "fold_metrics": metrics,
        "economic_validation": economics,
        "simulated_trades": trades,
        "horizon_summary": summary,
    }
    for key, table in tables.items():
        table.to_csv(config.output_root / files[key], index=False)

    candidate_horizons = summary.loc[summary["paper_trading_candidate"], "holding_period"].tolist()
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "dataset": str(config.dataset_path),
        "dataset_rows": dataset_rows,
        "horizons_analyzed": len(summary),
        "folds_completed": len(audits),
        "models_trained": (
            len(metrics) * len(model_catalog(config.random_seed)) * len(feature_sets())
        ),
        "paper_trading_candidates": candidate_horizons,
        "diagnostics_passed": diagnostics_passed,
    }
    signoff = {
        "phase": PHASE,
        "status": "PHASE12_RESEARCH_VALIDATION_COMPLETE",
        "diagnostics_passed": diagnostics_passed,
        "approved_for_paper_trading_review": approved,
        "approved_for_live_trading": False,
        "candidate_horizons": candidate_horizons,
        "blocked_horizons": summary.loc[
            ~summary["paper_trading_candidate"], "holding_period"
        ].tolist(),
        "notes": [
            "Model selection and probability calibration use pre-test data only.",
            "Walk-forward folds use purge and embargo gaps.",
            "Economic simulation prevents overlapping positions per symbol.",
            "Transaction costs and portfolio exposure constraints are applied.",
            "Approval permits paper-trading review only, never live trading.",
        ],
    }
    manifest = {
        "phase": PHASE,
        "version": VERSION,
        "artifacts": {key: str(config.output_root / value) for key, value in files.items()},
    }
    for name, payload in (("dashboard", dashboard), ("signoff", signoff), ("manifest", manifest)):
        (config.output_root / files[name]).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    return {key: str(config.output_root / value) for key, value in files.items()}
