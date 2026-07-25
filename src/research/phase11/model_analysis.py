from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src.research.phase11.features import FEATURE_COLUMNS

CATEGORICAL_COLUMNS = ("asset_class", "regime")
TARGET_COLUMN = "positive_return_label"
RETURN_COLUMN = "net_forward_return"


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    audit: pd.DataFrame


def chronological_sample(frame: pd.DataFrame, maximum_rows: int) -> pd.DataFrame:
    ordered = frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    if len(ordered) <= maximum_rows:
        return ordered
    indices = np.linspace(0, len(ordered) - 1, maximum_rows, dtype=int)
    return ordered.iloc[np.unique(indices)].reset_index(drop=True)


def purged_temporal_split(
    frame: pd.DataFrame,
    train_fraction: float,
    validation_fraction: float,
    purge_bars: int,
    embargo_bars: int,
) -> TemporalSplit:
    ordered = frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    timestamps = pd.Index(pd.to_datetime(ordered["timestamp"], utc=True).drop_duplicates())
    if len(timestamps) < 20:
        raise ValueError("at least 20 unique timestamps are required for temporal splitting")
    train_end = max(1, int(len(timestamps) * train_fraction))
    validation_end = max(
        train_end + 1,
        int(len(timestamps) * (train_fraction + validation_fraction)),
    )
    train_cut = timestamps[min(train_end - 1, len(timestamps) - 1)]
    validation_start_index = min(train_end + purge_bars, len(timestamps) - 1)
    validation_end_index = min(validation_end - 1, len(timestamps) - 1)
    test_start_index = min(validation_end + embargo_bars, len(timestamps) - 1)
    validation_start = timestamps[validation_start_index]
    validation_cut = timestamps[validation_end_index]
    test_start = timestamps[test_start_index]

    converted = pd.to_datetime(ordered["timestamp"], utc=True)
    train = ordered.loc[converted <= train_cut].copy()
    validation = ordered.loc[(converted >= validation_start) & (converted <= validation_cut)].copy()
    test = ordered.loc[converted >= test_start].copy()
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("temporal split produced an empty partition")

    audit = pd.DataFrame(
        [
            _partition_audit("train", train),
            _partition_audit("validation", validation),
            _partition_audit("test", test),
        ]
    )
    audit["chronology_passed"] = (
        pd.to_datetime(train["timestamp"], utc=True).max()
        < pd.to_datetime(validation["timestamp"], utc=True).min()
    ) & (
        pd.to_datetime(validation["timestamp"], utc=True).max()
        < pd.to_datetime(test["timestamp"], utc=True).min()
    )
    return TemporalSplit(train=train, validation=validation, test=test, audit=audit)


def _partition_audit(name: str, frame: pd.DataFrame) -> dict[str, object]:
    return {
        "partition": name,
        "rows": len(frame),
        "symbols": int(frame["symbol"].nunique()),
        "start_timestamp": str(pd.to_datetime(frame["timestamp"], utc=True).min()),
        "end_timestamp": str(pd.to_datetime(frame["timestamp"], utc=True).max()),
        "positive_rate": float(frame[TARGET_COLUMN].mean()),
    }


def model_catalog(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "dummy": DummyClassifier(strategy="prior"),
        "logistic_l2": LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=500,
            random_state=seed,
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=5,
            min_samples_leaf=100,
            class_weight="balanced",
            random_state=seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=160,
            max_depth=8,
            min_samples_leaf=50,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=160,
            max_leaf_nodes=15,
            min_samples_leaf=50,
            l2_regularization=1.0,
            random_state=seed,
        ),
    }


def build_pipeline(model: ClassifierMixin) -> Pipeline:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    preprocessing = ColumnTransformer(
        transformers=[
            ("numeric", numeric, list(FEATURE_COLUMNS)),
            ("categorical", categorical, list(CATEGORICAL_COLUMNS)),
        ],
        remainder="drop",
    )
    return Pipeline(steps=[("preprocessing", preprocessing), ("model", model)])


def predictor_columns() -> list[str]:
    return [*FEATURE_COLUMNS, *CATEGORICAL_COLUMNS]


def classification_metrics(
    y_true: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    labels = (probabilities >= threshold).astype(int)
    prevalence = float(y_true.mean())
    baseline_brier = float(brier_score_loss(y_true, np.full(len(y_true), prevalence)))
    brier = float(brier_score_loss(y_true, probabilities))
    return {
        "roc_auc": _safe_auc(y_true, probabilities),
        "average_precision": float(average_precision_score(y_true, probabilities)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, labels)),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "brier_score": brier,
        "baseline_brier": baseline_brier,
        "brier_improvement": baseline_brier - brier,
        "prediction_positive_rate": float(labels.mean()),
    }


def _safe_auc(y_true: pd.Series, probabilities: np.ndarray) -> float:
    if y_true.nunique() < 2:
        return 0.5
    return float(roc_auc_score(y_true, probabilities))


def threshold_economics(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    thresholds: tuple[float, ...],
) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    returns = frame[RETURN_COLUMN].to_numpy(dtype=float)
    for threshold in thresholds:
        selected = probabilities >= threshold
        selected_returns = returns[selected]
        trades = int(selected.sum())
        rows.append(
            {
                "threshold": threshold,
                "trades": trades,
                "trade_rate": float(selected.mean()),
                "win_rate": float((selected_returns > 0.0).mean()) if trades else 0.0,
                "mean_net_return": float(selected_returns.mean()) if trades else 0.0,
                "median_net_return": float(np.median(selected_returns)) if trades else 0.0,
                "cumulative_return": _compounded_return(selected_returns),
                "maximum_drawdown": _maximum_drawdown(selected_returns),
                "return_to_drawdown": _return_to_drawdown(selected_returns),
            }
        )
    return pd.DataFrame(rows)


def _compounded_return(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    clipped = np.clip(returns, -0.999, None)
    log_growth = float(np.log1p(clipped).sum())
    safe_log_growth = min(log_growth, 700.0)
    return float(np.expm1(safe_log_growth))


def _maximum_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    clipped = np.clip(returns, -0.999, None)
    log_equity = np.cumsum(np.log1p(clipped))
    running_peak = np.maximum.accumulate(log_equity)
    relative_equity = np.exp(np.minimum(log_equity - running_peak, 0.0))
    drawdowns = 1.0 - relative_equity
    return float(drawdowns.max(initial=0.0))


def _return_to_drawdown(returns: np.ndarray) -> float:
    compounded = _compounded_return(returns)
    drawdown = _maximum_drawdown(returns)
    if drawdown <= 1e-9:
        return compounded
    return float(min(compounded / drawdown, np.finfo(float).max))


def calibration_table(y_true: pd.Series, probabilities: np.ndarray, bins: int = 10) -> pd.DataFrame:
    result = pd.DataFrame({"actual": y_true.to_numpy(dtype=int), "probability": probabilities})
    bin_edges = [float(value) for value in np.linspace(0.0, 1.0, bins + 1)]
    result["bin"] = pd.cut(
        result["probability"],
        bins=bin_edges,
        include_lowest=True,
    )
    grouped = (
        result.groupby("bin", observed=True)
        .agg(
            rows=("actual", "size"),
            mean_probability=("probability", "mean"),
            actual_rate=("actual", "mean"),
        )
        .reset_index()
    )
    grouped["calibration_error"] = (grouped["mean_probability"] - grouped["actual_rate"]).abs()
    grouped["bin"] = grouped["bin"].astype(str)
    return grouped


def feature_importance_table(pipeline: Pipeline) -> pd.DataFrame:
    preprocessing = pipeline.named_steps["preprocessing"]
    model = pipeline.named_steps["model"]
    names = [str(value) for value in preprocessing.get_feature_names_out()]
    values: np.ndarray
    if hasattr(model, "feature_importances_"):
        values = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        values = np.abs(np.asarray(model.coef_, dtype=float)).mean(axis=0)
    else:
        values = np.zeros(len(names), dtype=float)
    return pd.DataFrame({"feature": names, "importance": values}).sort_values(
        "importance", ascending=False, kind="stable"
    )


def subgroup_metrics(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    threshold: float,
    group_column: str,
) -> pd.DataFrame:
    working = frame.reset_index(drop=True).copy()
    working["probability"] = probabilities
    rows: list[dict[str, Any]] = []
    for group, group_frame in working.groupby(group_column, observed=True):
        metrics = classification_metrics(
            group_frame[TARGET_COLUMN], group_frame["probability"].to_numpy(dtype=float), threshold
        )
        rows.append({group_column: str(group), "rows": len(group_frame), **metrics})
    return pd.DataFrame(rows)
