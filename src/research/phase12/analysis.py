from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.research.phase11.features import FEATURE_COLUMNS

TARGET_COLUMN = "positive_return_label"
RETURN_COLUMN = "net_forward_return"


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train: pd.DataFrame
    calibration: pd.DataFrame
    test: pd.DataFrame
    audit: dict[str, object]


@dataclass(frozen=True)
class PlattCalibrator:
    intercept: float
    coefficient: float

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        clipped = np.clip(probabilities, 1e-6, 1.0 - 1e-6)
        logits = np.log(clipped / (1.0 - clipped))
        values = self.intercept + self.coefficient * logits
        calibrated = 1.0 / (1.0 + np.exp(-np.clip(values, -35.0, 35.0)))
        return np.asarray(calibrated, dtype=float)


def chronological_sample(frame: pd.DataFrame, maximum_rows: int) -> pd.DataFrame:
    ordered = frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    if len(ordered) <= maximum_rows:
        return ordered
    indices = np.linspace(0, len(ordered) - 1, maximum_rows, dtype=int)
    return ordered.iloc[np.unique(indices)].reset_index(drop=True)


def expanding_walk_forward_folds(
    frame: pd.DataFrame,
    fold_count: int,
    minimum_train_timestamps: int,
    calibration_fraction: float,
    test_fraction: float,
    purge_bars: int,
    embargo_bars: int,
) -> list[WalkForwardFold]:
    ordered = frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    converted = pd.to_datetime(ordered["timestamp"], utc=True)
    timestamps = pd.Index(converted.drop_duplicates())
    calibration_size = max(10, int(len(timestamps) * calibration_fraction))
    test_size = max(10, int(len(timestamps) * test_fraction))
    required = minimum_train_timestamps + calibration_size + test_size + purge_bars + embargo_bars
    if len(timestamps) < required:
        raise ValueError("insufficient timestamps for requested walk-forward configuration")

    available = len(timestamps) - required
    step = max(1, available // max(1, fold_count - 1))
    folds: list[WalkForwardFold] = []
    for fold_index in range(fold_count):
        train_end_index = minimum_train_timestamps - 1 + fold_index * step
        calibration_start_index = train_end_index + 1 + purge_bars
        calibration_end_index = calibration_start_index + calibration_size - 1
        test_start_index = calibration_end_index + 1 + embargo_bars
        test_end_index = test_start_index + test_size - 1
        if test_end_index >= len(timestamps):
            break

        train_end = timestamps[train_end_index]
        calibration_start = timestamps[calibration_start_index]
        calibration_end = timestamps[calibration_end_index]
        test_start = timestamps[test_start_index]
        test_end = timestamps[test_end_index]
        train = ordered.loc[converted <= train_end].copy()
        calibration = ordered.loc[
            (converted >= calibration_start) & (converted <= calibration_end)
        ].copy()
        test = ordered.loc[(converted >= test_start) & (converted <= test_end)].copy()
        chronology = (
            pd.to_datetime(train["timestamp"], utc=True).max()
            < pd.to_datetime(calibration["timestamp"], utc=True).min()
            < pd.to_datetime(test["timestamp"], utc=True).min()
        )
        folds.append(
            WalkForwardFold(
                fold=fold_index + 1,
                train=train,
                calibration=calibration,
                test=test,
                audit={
                    "fold": fold_index + 1,
                    "train_rows": len(train),
                    "calibration_rows": len(calibration),
                    "test_rows": len(test),
                    "train_end": str(train_end),
                    "calibration_start": str(calibration_start),
                    "calibration_end": str(calibration_end),
                    "test_start": str(test_start),
                    "test_end": str(test_end),
                    "chronology_passed": bool(chronology),
                },
            )
        )
    if len(folds) < 2:
        raise ValueError("walk-forward configuration produced fewer than two folds")
    return folds


def model_catalog(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "logistic_l2": LogisticRegression(
            C=0.5,
            class_weight="balanced",
            max_iter=500,
            random_state=seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=180,
            max_depth=8,
            min_samples_leaf=50,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=180,
            max_leaf_nodes=15,
            min_samples_leaf=50,
            l2_regularization=1.5,
            random_state=seed,
        ),
    }


def feature_sets() -> dict[str, tuple[str, ...]]:
    return {
        "all_features": tuple(FEATURE_COLUMNS),
        "trend_momentum": (
            "return_1",
            "momentum_5",
            "momentum_21",
            "trend_fast_slow",
            "trend_50_200",
            "rsi_14",
            "ema_20_distance",
            "ema_50_distance",
            "sma_20_slope_5",
            "roc_10",
            "macd_histogram",
            "breakout_20",
        ),
        "volatility_structure": (
            "annualized_volatility",
            "atr_percent",
            "drawdown",
            "bollinger_width_20",
            "distance_to_20d_high",
            "distance_to_20d_low",
            "relative_volume",
            "volume_change_5",
            "obv_slope_10",
        ),
    }


def build_pipeline(model: ClassifierMixin, columns: tuple[str, ...]) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", model),
        ]
    )


def fit_platt_calibrator(probabilities: np.ndarray, labels: pd.Series) -> PlattCalibrator:
    clipped = np.clip(probabilities, 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    if labels.nunique() < 2:
        prevalence = float(labels.mean())
        intercept = float(np.log(np.clip(prevalence, 1e-6, 1.0 - 1e-6) / (1.0 - prevalence)))
        return PlattCalibrator(intercept=intercept, coefficient=0.0)
    calibrator = LogisticRegression(C=1.0, max_iter=300)
    calibrator.fit(logits, labels.to_numpy(dtype=int))
    return PlattCalibrator(
        intercept=float(calibrator.intercept_[0]),
        coefficient=float(calibrator.coef_[0, 0]),
    )


def probability_metrics(labels: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    prevalence = float(labels.mean())
    baseline = np.full(len(labels), prevalence)
    brier = float(brier_score_loss(labels, probabilities))
    baseline_brier = float(brier_score_loss(labels, baseline))
    auc = 0.5 if labels.nunique() < 2 else float(roc_auc_score(labels, probabilities))
    return {
        "roc_auc": auc,
        "brier_score": brier,
        "baseline_brier": baseline_brier,
        "brier_improvement": baseline_brier - brier,
    }


def realistic_portfolio_simulation(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    threshold: float,
    holding_period: int,
    initial_capital: float,
    maximum_open_positions: int,
    allocation_per_trade: float,
    slippage_bps: float,
    commission_bps: float,
) -> tuple[dict[str, float | int], pd.DataFrame]:
    candidates = frame[["timestamp", "symbol", RETURN_COLUMN]].copy()
    candidates["probability"] = probabilities
    candidates = candidates.loc[candidates["probability"] >= threshold]
    candidates = candidates.sort_values(
        ["timestamp", "probability", "symbol"], ascending=[True, False, True], kind="stable"
    )
    symbol_steps = frame.sort_values(["symbol", "timestamp"], kind="stable").copy()
    symbol_steps["symbol_step"] = symbol_steps.groupby("symbol").cumcount()
    candidates = candidates.join(symbol_steps["symbol_step"])

    next_available: dict[str, int] = {}
    accepted: list[dict[str, Any]] = []
    cost = (slippage_bps + commission_bps) / 10_000.0
    for _, row in candidates.iterrows():
        symbol = str(row["symbol"])
        step = int(row["symbol_step"])
        if step < next_available.get(symbol, -1):
            continue
        same_time = sum(1 for item in accepted if item["timestamp"] == row["timestamp"])
        if same_time >= maximum_open_positions:
            continue
        gross_return = float(row[RETURN_COLUMN])
        net_return = max(-0.999, gross_return - 2.0 * cost)
        accepted.append(
            {
                "timestamp": row["timestamp"],
                "symbol": symbol,
                "probability": float(row["probability"]),
                "gross_return": gross_return,
                "net_return_after_costs": net_return,
            }
        )
        next_available[symbol] = step + holding_period

    trades = pd.DataFrame(accepted)
    if trades.empty:
        return _empty_economics(initial_capital, threshold), trades

    grouped = trades.groupby("timestamp", sort=True)["net_return_after_costs"].mean()
    exposure = min(1.0, maximum_open_positions * allocation_per_trade)
    portfolio_returns = grouped.to_numpy(dtype=float) * exposure
    equity = initial_capital * np.cumprod(1.0 + np.clip(portfolio_returns, -0.999, None))
    peaks = np.maximum.accumulate(np.concatenate(([initial_capital], equity)))
    equity_with_start = np.concatenate(([initial_capital], equity))
    drawdowns = 1.0 - equity_with_start / np.maximum(peaks, 1e-12)
    ending_capital = float(equity[-1])
    total_return = ending_capital / initial_capital - 1.0
    return (
        {
            "threshold": threshold,
            "trades": len(trades),
            "win_rate": float((trades["net_return_after_costs"] > 0.0).mean()),
            "mean_trade_return": float(trades["net_return_after_costs"].mean()),
            "total_return": float(total_return),
            "ending_capital": ending_capital,
            "maximum_drawdown": float(np.nanmax(drawdowns)),
            "return_to_drawdown": float(total_return / max(float(np.nanmax(drawdowns)), 1e-12)),
        },
        trades,
    )


def _empty_economics(initial_capital: float, threshold: float) -> dict[str, float | int]:
    return {
        "threshold": threshold,
        "trades": 0,
        "win_rate": 0.0,
        "mean_trade_return": 0.0,
        "total_return": 0.0,
        "ending_capital": initial_capital,
        "maximum_drawdown": 0.0,
        "return_to_drawdown": 0.0,
    }
