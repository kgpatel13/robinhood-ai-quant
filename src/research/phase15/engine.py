from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.research.phase14.engine import infer_asset_class
from src.research.phase15.models import Phase15Config, Phase15Result

PHASE = "15.0-15.9"
VERSION = "0.15.0"
TARGET = "profitable"
NUMERIC_FEATURES = (
    "probability",
    "holding_period",
    "fold",
    "year",
    "month",
    "day_of_week",
    "probability_edge",
    "symbol_history_count",
    "symbol_prior_win_rate",
    "symbol_prior_mean_return",
    "asset_prior_win_rate",
    "asset_prior_mean_return",
    "market_prior_win_rate",
    "market_prior_mean_return",
)
CATEGORICAL_FEATURES = ("symbol", "asset_class", "market_regime")


def _safe_auc(target: pd.Series, probability: np.ndarray) -> float:
    return float(roc_auc_score(target, probability)) if target.nunique() > 1 else 0.5


def _maximum_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.astype(float)).cumprod()
    peak = equity.cummax()
    drawdown = 1.0 - equity / peak.replace(0.0, np.nan)
    return float(drawdown.fillna(0.0).max())


def _profit_factor(returns: pd.Series) -> float:
    wins = float(returns[returns > 0.0].sum())
    losses = float(-returns[returns < 0.0].sum())
    return wins / losses if losses > 0.0 else 0.0


def _prepare_features(raw: pd.DataFrame) -> pd.DataFrame:
    required = {
        "holding_period",
        "fold",
        "timestamp",
        "symbol",
        "probability",
        "net_return_after_costs",
    }
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"trades are missing required columns: {missing}")
    frame = raw.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values(["timestamp", "symbol", "holding_period"]).reset_index(drop=True)
    frame["asset_class"] = frame["symbol"].astype(str).map(infer_asset_class)
    frame["year"] = frame["timestamp"].dt.year.astype(float)
    frame["month"] = frame["timestamp"].dt.month.astype(float)
    frame["day_of_week"] = frame["timestamp"].dt.dayofweek.astype(float)
    frame["probability_edge"] = frame["probability"].astype(float) - 0.5
    frame[TARGET] = (frame["net_return_after_costs"].astype(float) > 0.0).astype(int)

    market_prior = frame[TARGET].shift(1).expanding().mean().fillna(0.5)
    market_return = (
        frame["net_return_after_costs"].astype(float).shift(1).expanding().mean().fillna(0.0)
    )
    frame["market_prior_win_rate"] = market_prior
    frame["market_prior_mean_return"] = market_return
    rolling = market_return.rolling(100, min_periods=20).mean().fillna(market_return)
    frame["market_regime"] = np.where(
        rolling > 0.002,
        "bull",
        np.where(rolling < -0.002, "bear", "sideways"),
    )

    symbol_group = frame.groupby("symbol", sort=False)
    frame["symbol_history_count"] = symbol_group.cumcount().astype(float)
    frame["symbol_prior_win_rate"] = (
        symbol_group[TARGET]
        .transform(lambda values: values.shift(1).expanding().mean())
        .fillna(0.5)
    )
    frame["symbol_prior_mean_return"] = (
        symbol_group["net_return_after_costs"]
        .transform(lambda values: values.astype(float).shift(1).expanding().mean())
        .fillna(0.0)
    )

    asset_group = frame.groupby("asset_class", sort=False)
    frame["asset_prior_win_rate"] = (
        asset_group[TARGET].transform(lambda values: values.shift(1).expanding().mean()).fillna(0.5)
    )
    frame["asset_prior_mean_return"] = (
        asset_group["net_return_after_costs"]
        .transform(lambda values: values.astype(float).shift(1).expanding().mean())
        .fillna(0.0)
    )
    return frame


def _pipeline(classifier: ClassifierMixin) -> Pipeline:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    transformer = ColumnTransformer(
        [
            ("numeric", numeric, list(NUMERIC_FEATURES)),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ]
    )
    return Pipeline([("features", transformer), ("classifier", classifier)])


def _catalog(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "logistic": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed),
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=20,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=250,
            max_depth=10,
            min_samples_leaf=15,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=seed,
        ),
    }


def _fold_boundaries(
    rows: int, folds: int, validation_fraction: float, test_fraction: float
) -> list[tuple[int, int, int]]:
    test_size = max(int(rows * test_fraction), 1)
    validation_size = max(int(rows * validation_fraction), 1)
    earliest_test = rows - folds * test_size
    boundaries: list[tuple[int, int, int]] = []
    for index in range(folds):
        test_start = earliest_test + index * test_size
        validation_start = test_start - validation_size
        test_end = min(test_start + test_size, rows)
        if validation_start > 0 and test_start < test_end:
            boundaries.append((validation_start, test_start, test_end))
    return boundaries


def _threshold_economics(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    thresholds: tuple[float, ...],
    cost_bps: float,
) -> pd.DataFrame:
    records: list[dict[str, float | int]] = []
    returns = frame["net_return_after_costs"].astype(float).to_numpy()
    extra_cost = cost_bps / 10_000.0
    for threshold in thresholds:
        selected = probabilities >= threshold
        selected_returns = pd.Series(returns[selected] - extra_cost, dtype=float)
        records.append(
            {
                "threshold": threshold,
                "trades": int(selected.sum()),
                "win_rate": (
                    float((selected_returns > 0.0).mean()) if len(selected_returns) else 0.0
                ),
                "mean_return": float(selected_returns.mean()) if len(selected_returns) else 0.0,
                "total_return": (
                    float(np.prod(1.0 + selected_returns.to_numpy(dtype=float)) - 1.0)
                    if len(selected_returns)
                    else 0.0
                ),
                "profit_factor": _profit_factor(selected_returns),
                "maximum_drawdown": _maximum_drawdown(selected_returns),
            }
        )
    return pd.DataFrame(records)


def _feature_importance(model: Pipeline) -> pd.DataFrame:
    transformer = model.named_steps["features"]
    classifier = model.named_steps["classifier"]
    names = transformer.get_feature_names_out()
    if hasattr(classifier, "feature_importances_"):
        values = np.asarray(classifier.feature_importances_, dtype=float)
    elif hasattr(classifier, "coef_"):
        values = np.abs(np.asarray(classifier.coef_, dtype=float)[0])
    else:
        values = np.zeros(len(names), dtype=float)
    result = pd.DataFrame({"feature": names.astype(str), "importance": values})
    total = float(result["importance"].sum())
    result["importance_share"] = result["importance"] / total if total > 0.0 else 0.0
    return result.sort_values("importance", ascending=False).reset_index(drop=True)


def _group_performance(scored: pd.DataFrame, column: str, threshold: float) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for key, group in scored.groupby(column, dropna=False):
        selected = group.loc[group["alpha_probability"] >= threshold]
        returns = selected["net_return_after_costs"].astype(float)
        records.append(
            {
                column: str(key),
                "source_trades": int(len(group)),
                "selected_trades": int(len(selected)),
                "selection_rate": float(len(selected) / len(group)) if len(group) else 0.0,
                "win_rate": float((returns > 0.0).mean()) if len(returns) else 0.0,
                "mean_return": float(returns.mean()) if len(returns) else 0.0,
                "profit_factor": _profit_factor(returns),
                "maximum_drawdown": _maximum_drawdown(returns),
            }
        )
    return pd.DataFrame(records)


def run_phase15(config: Phase15Config) -> Phase15Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    frame = _prepare_features(pd.read_csv(config.trades_path))
    features = list(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    unique_timestamps = pd.Index(frame["timestamp"].drop_duplicates().sort_values())
    boundaries = _fold_boundaries(
        len(unique_timestamps),
        config.folds,
        config.validation_fraction,
        config.test_fraction,
    )
    if not boundaries:
        raise ValueError("insufficient rows for Phase 15 walk-forward analysis")

    metric_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    champion_counts: dict[str, int] = {}
    models_trained = 0
    last_models: dict[str, Pipeline] = {}

    for fold_number, (validation_start, test_start, test_end) in enumerate(boundaries, start=1):
        validation_timestamp = unique_timestamps[validation_start]
        test_timestamp = unique_timestamps[test_start]
        test_end_timestamp = unique_timestamps[test_end - 1]
        train = frame.loc[frame["timestamp"] < validation_timestamp]
        validation = frame.loc[
            (frame["timestamp"] >= validation_timestamp) & (frame["timestamp"] < test_timestamp)
        ]
        test = frame.loc[
            (frame["timestamp"] >= test_timestamp) & (frame["timestamp"] <= test_end_timestamp)
        ]
        if len(train) < config.minimum_train_rows:
            continue
        candidates: list[tuple[str, Pipeline, float, float, float]] = []
        for model_name, classifier in _catalog(config.random_seed + fold_number).items():
            model = _pipeline(classifier)
            model.fit(train[features], train[TARGET])
            models_trained += 1
            validation_probability = model.predict_proba(validation[features])[:, 1]
            auc = _safe_auc(validation[TARGET], validation_probability)
            brier = float(brier_score_loss(validation[TARGET], validation_probability))
            score = auc - brier
            candidates.append((model_name, model, score, auc, brier))
        champion_name, champion, selection_score, validation_auc, validation_brier = max(
            candidates, key=lambda item: item[2]
        )
        champion_counts[champion_name] = champion_counts.get(champion_name, 0) + 1
        last_models[champion_name] = champion
        test_probability = champion.predict_proba(test[features])[:, 1]
        test_auc = _safe_auc(test[TARGET], test_probability)
        test_brier = float(brier_score_loss(test[TARGET], test_probability))
        metric_rows.append(
            {
                "fold": fold_number,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "test_rows": len(test),
                "champion_model": champion_name,
                "selection_score": selection_score,
                "validation_auc": validation_auc,
                "validation_brier": validation_brier,
                "test_auc": test_auc,
                "test_brier": test_brier,
                "chronology_passed": bool(
                    train["timestamp"].max()
                    < validation["timestamp"].min()
                    <= test["timestamp"].min()
                ),
            }
        )
        scored = test.copy()
        scored["alpha_probability"] = test_probability
        scored["phase15_fold"] = fold_number
        scored["champion_model"] = champion_name
        prediction_frames.append(scored)

    if not prediction_frames:
        raise ValueError("no Phase 15 folds met the minimum training requirement")
    metrics = pd.DataFrame(metric_rows)
    scored = pd.concat(prediction_frames, ignore_index=True).sort_values("timestamp")
    ensemble_champion = max(champion_counts, key=lambda name: champion_counts[name])
    economics = _threshold_economics(
        scored,
        scored["alpha_probability"].to_numpy(dtype=float),
        config.probability_thresholds,
        config.transaction_cost_bps,
    )
    eligible = economics.loc[economics["trades"] >= config.minimum_test_trades]
    pool = eligible if not eligible.empty else economics
    selected_row = pool.sort_values(
        ["profit_factor", "mean_return", "maximum_drawdown"], ascending=[False, False, True]
    ).iloc[0]
    selected_threshold = float(selected_row["threshold"])

    final_classifier = _catalog(config.random_seed)[ensemble_champion]
    final_model = _pipeline(final_classifier)
    final_model.fit(frame[features], frame[TARGET])
    models_trained += 1
    model_path = config.output_root / "phase15_champion.joblib"
    joblib.dump(final_model, model_path)

    importance = _feature_importance(final_model)
    asset = _group_performance(scored, "asset_class", selected_threshold)
    symbol = _group_performance(scored, "symbol", selected_threshold)
    regime = _group_performance(scored, "market_regime", selected_threshold)
    alpha_probabilities = scored["alpha_probability"].astype(float)
    probability_bins = pd.cut(
        alpha_probabilities,
        bins=list(np.linspace(0.0, 1.0, 11)),
        include_lowest=True,
    )
    calibration = (
        scored.assign(probability_bin=probability_bins)
        .groupby("probability_bin", observed=True)
        .agg(
            rows=(TARGET, "size"),
            predicted_probability=("alpha_probability", "mean"),
            observed_win_rate=(TARGET, "mean"),
            mean_return=("net_return_after_costs", "mean"),
        )
        .reset_index()
    )
    calibration["probability_bin"] = calibration["probability_bin"].astype(str)

    diagnostics_passed = (
        bool(metrics["chronology_passed"].all()) and not scored["alpha_probability"].isna().any()
    )
    median_auc = float(metrics["test_auc"].median())
    selected_profit_factor = float(selected_row["profit_factor"])
    selected_drawdown = float(selected_row["maximum_drawdown"])
    approved = (
        diagnostics_passed
        and median_auc >= config.minimum_auc
        and int(selected_row["trades"]) >= config.minimum_test_trades
        and selected_profit_factor >= config.minimum_profit_factor
        and selected_drawdown <= config.maximum_drawdown
    )

    files = {
        "walk_forward_metrics": "walk_forward_metrics.csv",
        "threshold_economics": "threshold_economics.csv",
        "scored_trades": "scored_trades.csv",
        "calibration": "probability_calibration.csv",
        "feature_importance": "feature_importance.csv",
        "asset_policy": "asset_class_policy.csv",
        "symbol_policy": "symbol_policy.csv",
        "regime_policy": "regime_policy.csv",
        "champion_model": model_path.name,
        "dashboard": "phase15_dashboard.json",
        "signoff": "phase15_final_signoff.json",
        "manifest": "manifest.json",
    }
    tables = {
        "walk_forward_metrics": metrics,
        "threshold_economics": economics,
        "scored_trades": scored,
        "calibration": calibration,
        "feature_importance": importance,
        "asset_policy": asset,
        "symbol_policy": symbol,
        "regime_policy": regime,
    }
    for key, table in tables.items():
        table.to_csv(config.output_root / files[key], index=False)

    dashboard: dict[str, object] = {
        "phase": PHASE,
        "version": VERSION,
        "source_trades": len(frame),
        "out_of_sample_trades": len(scored),
        "folds_completed": len(metrics),
        "models_trained": models_trained,
        "champion_model": ensemble_champion,
        "champion_fold_counts": champion_counts,
        "selected_threshold": selected_threshold,
        "median_test_auc": median_auc,
        "mean_test_brier": float(metrics["test_brier"].mean()),
        "selected_trades": int(selected_row["trades"]),
        "selected_win_rate": float(selected_row["win_rate"]),
        "selected_mean_return": float(selected_row["mean_return"]),
        "selected_profit_factor": selected_profit_factor,
        "selected_maximum_drawdown": selected_drawdown,
        "diagnostics_passed": diagnostics_passed,
        "approved_for_phase16_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    (config.output_root / files["dashboard"]).write_text(
        json.dumps(dashboard, indent=2), encoding="utf-8"
    )
    signoff = {
        "phase": PHASE,
        "status": "PHASE15_AI_ALPHA_ENGINE_COMPLETE",
        "diagnostics_passed": diagnostics_passed,
        "approved_for_phase16_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "notes": [
            "All reported model performance is out-of-sample and chronologically ordered.",
            "Phase 15 is a meta-labeling alpha layer over Phase 12 trade candidates.",
            "Champion selection uses validation data only; test folds remain untouched "
            "until scoring.",
            "Asset-class, symbol, and regime policies are diagnostic and do not submit orders.",
            "Paper and live trading remain disabled regardless of the Phase 16 review gate.",
        ],
    }
    (config.output_root / files["signoff"]).write_text(
        json.dumps(signoff, indent=2), encoding="utf-8"
    )
    manifest: dict[str, Any] = {
        "phase": PHASE,
        "version": VERSION,
        "config": asdict(config),
        "artifacts": {key: str(config.output_root / value) for key, value in files.items()},
    }
    manifest["config"]["trades_path"] = str(config.trades_path)
    manifest["config"]["output_root"] = str(config.output_root)
    manifest["config"]["probability_thresholds"] = list(config.probability_thresholds)
    (config.output_root / files["manifest"]).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return Phase15Result(
        source_trades=len(frame),
        folds_completed=len(metrics),
        models_trained=models_trained,
        champion_model=ensemble_champion,
        selected_threshold=selected_threshold,
        diagnostics_passed=diagnostics_passed,
        approved_for_phase16_review=approved,
        approved_for_paper_trading=False,
        approved_for_live_trading=False,
        output=str(config.output_root),
        artifacts={key: str(config.output_root / value) for key, value in files.items()},
    )
