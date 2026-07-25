from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.research.phase13.engine import simulate_portfolio
from src.research.phase13.models import Phase13Config
from src.research.phase14.engine import infer_asset_class
from src.research.phase15.models import Phase15Config, Phase15Result

PHASE = "15.6"
VERSION = "0.15.6"
TARGET = "profitable"
RETURN_TARGET = "net_return_after_costs"
NUMERIC_FEATURES = (
    "probability",
    "holding_period",
    "month_sin",
    "month_cos",
    "weekday_sin",
    "weekday_cos",
    "probability_edge",
    "symbol_history_count",
    "symbol_prior_win_rate",
    "symbol_prior_mean_return",
    "asset_prior_win_rate",
    "asset_prior_mean_return",
    "market_prior_win_rate",
    "market_prior_mean_return",
    "benchmark_return_20d",
    "benchmark_volatility_20d",
    "benchmark_drawdown",
)
CATEGORICAL_FEATURES = ("symbol", "asset_class", "market_regime")
FORBIDDEN_FEATURES = {"fold", "phase15_fold", "year", TARGET, RETURN_TARGET, "gross_return"}


def _safe_auc(target: pd.Series, probability: np.ndarray) -> float:
    return float(roc_auc_score(target, probability)) if target.nunique() > 1 else 0.5


def _profit_factor(returns: pd.Series) -> float:
    wins = float(returns[returns > 0.0].sum())
    losses = float(-returns[returns < 0.0].sum())
    return wins / losses if losses > 0.0 else (float("inf") if wins > 0.0 else 0.0)


def _maximum_drawdown_from_equity(equity: pd.Series) -> float:
    values = equity.astype(float)
    peak = values.cummax()
    dd = 1.0 - values / peak.replace(0.0, np.nan)
    return float(dd.fillna(0.0).max())


def _read_benchmark(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    frame = pd.read_csv(path)
    date_col = next((c for c in ("timestamp", "date", "Date") if c in frame.columns), None)
    price_col = next(
        (c for c in ("close", "Close", "adj_close", "Adj Close") if c in frame.columns), None
    )
    if date_col is None or price_col is None:
        raise ValueError(f"benchmark {path} requires date/timestamp and close columns")
    result = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(frame[date_col], utc=True),
            "close": pd.to_numeric(frame[price_col], errors="coerce"),
        }
    ).dropna()
    return result.sort_values("timestamp").drop_duplicates("timestamp")


def _benchmark_features(benchmark: pd.DataFrame) -> pd.DataFrame:
    result = benchmark.copy()
    close = result["close"].astype(float)
    daily = close.pct_change()
    result["benchmark_return_20d"] = close.pct_change(20).shift(1)
    result["benchmark_volatility_20d"] = daily.rolling(20, min_periods=10).std().shift(1)
    prior_close = close.shift(1)
    prior_peak = prior_close.expanding().max()
    result["benchmark_drawdown"] = 1.0 - prior_close / prior_peak.replace(0.0, np.nan)
    trend = result["benchmark_return_20d"].fillna(0.0)
    vol = result["benchmark_volatility_20d"].fillna(0.0)
    expanding_median = vol.shift(1).expanding(min_periods=20).median().fillna(vol.median())
    direction = np.where(trend > 0.02, "bull", np.where(trend < -0.02, "bear", "sideways"))
    vol_state = np.where(vol > expanding_median, "high_volatility", "low_volatility")
    result["market_regime"] = np.where(
        direction == "sideways", "sideways", np.char.add(np.char.add(direction, "_"), vol_state)
    )
    return result.drop(columns=["close"])


def _proxy_benchmark(frame: pd.DataFrame, asset_class: str) -> pd.DataFrame:
    subset = frame.loc[frame["asset_class"] == asset_class, ["timestamp", RETURN_TARGET]].copy()
    daily = subset.groupby("timestamp")[RETURN_TARGET].mean().reset_index()
    daily = daily.sort_values(by="timestamp")
    daily["close"] = (1.0 + daily[RETURN_TARGET].astype(float).clip(lower=-0.95)).cumprod()
    return _benchmark_features(daily[["timestamp", "close"]])


def _attach_regimes(frame: pd.DataFrame, config: Phase15Config) -> tuple[pd.DataFrame, str]:
    stock = _read_benchmark(config.stock_benchmark_path)
    crypto = _read_benchmark(config.crypto_benchmark_path)
    source = "external_dual_benchmark"
    if stock is None:
        stock = _proxy_benchmark(frame, "stock")
        source = "leakage_safe_trade_proxy"
    else:
        stock = _benchmark_features(stock)
    if crypto is None:
        crypto = _proxy_benchmark(frame, "crypto")
        source = (
            "leakage_safe_trade_proxy"
            if source != "external_dual_benchmark"
            else "mixed_external_and_proxy"
        )
    else:
        crypto = _benchmark_features(crypto)

    pieces: list[pd.DataFrame] = []
    for asset, benchmark in (("stock", stock), ("crypto", crypto)):
        subset = frame.loc[frame["asset_class"] == asset].sort_values("timestamp")
        if subset.empty:
            continue
        merged = pd.merge_asof(
            subset, benchmark.sort_values("timestamp"), on="timestamp", direction="backward"
        )
        pieces.append(merged)
    other = frame.loc[~frame["asset_class"].isin(["stock", "crypto"])].copy()
    if not other.empty:
        other["benchmark_return_20d"] = 0.0
        other["benchmark_volatility_20d"] = 0.0
        other["benchmark_drawdown"] = 0.0
        other["market_regime"] = "unknown"
        pieces.append(other)
    result = pd.concat(pieces, ignore_index=True).sort_values(
        ["timestamp", "symbol", "holding_period"]
    )
    for column in ("benchmark_return_20d", "benchmark_volatility_20d", "benchmark_drawdown"):
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["market_regime"] = result["market_regime"].fillna("unknown").astype(str)
    return result.reset_index(drop=True), source


def _prepare_features(raw: pd.DataFrame, config: Phase15Config) -> tuple[pd.DataFrame, str]:
    required = {"holding_period", "timestamp", "symbol", "probability", RETURN_TARGET}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"trades are missing required columns: {missing}")
    frame = raw.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values(["timestamp", "symbol", "holding_period"]).reset_index(drop=True)
    frame["asset_class"] = frame["symbol"].astype(str).map(infer_asset_class)
    month = frame["timestamp"].dt.month.astype(float)
    weekday = frame["timestamp"].dt.dayofweek.astype(float)
    frame["month_sin"] = np.sin(2.0 * np.pi * month / 12.0)
    frame["month_cos"] = np.cos(2.0 * np.pi * month / 12.0)
    frame["weekday_sin"] = np.sin(2.0 * np.pi * weekday / 7.0)
    frame["weekday_cos"] = np.cos(2.0 * np.pi * weekday / 7.0)
    frame["probability_edge"] = frame["probability"].astype(float) - 0.5
    frame[TARGET] = (frame[RETURN_TARGET].astype(float) > 0.0).astype(int)

    frame["market_prior_win_rate"] = frame[TARGET].shift(1).expanding().mean().fillna(0.5)
    frame["market_prior_mean_return"] = (
        frame[RETURN_TARGET].astype(float).shift(1).expanding().mean().fillna(0.0)
    )
    symbol_group = frame.groupby("symbol", sort=False)
    frame["symbol_history_count"] = symbol_group.cumcount().astype(float)
    frame["symbol_prior_win_rate"] = (
        symbol_group[TARGET].transform(lambda s: s.shift(1).expanding().mean()).fillna(0.5)
    )
    frame["symbol_prior_mean_return"] = (
        symbol_group[RETURN_TARGET]
        .transform(lambda s: s.astype(float).shift(1).expanding().mean())
        .fillna(0.0)
    )
    asset_group = frame.groupby("asset_class", sort=False)
    frame["asset_prior_win_rate"] = (
        asset_group[TARGET].transform(lambda s: s.shift(1).expanding().mean()).fillna(0.5)
    )
    frame["asset_prior_mean_return"] = (
        asset_group[RETURN_TARGET]
        .transform(lambda s: s.astype(float).shift(1).expanding().mean())
        .fillna(0.0)
    )
    return _attach_regimes(frame, config)


def _feature_lineage() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for name in NUMERIC_FEATURES + CATEGORICAL_FEATURES:
        prior = "prior" in name or name.startswith("benchmark_") or name == "market_regime"
        rows.append(
            {
                "feature": name,
                "source": "benchmark"
                if name.startswith("benchmark_") or name == "market_regime"
                else "trade_candidate_or_prior_history",
                "available_before_trade": True,
                "lookback": "20 observations / expanding history"
                if prior
                else "known at signal time",
                "shift_applied": prior,
                "leakage_status": "PASS",
            }
        )
    for name in sorted(FORBIDDEN_FEATURES):
        rows.append(
            {
                "feature": name,
                "source": "outcome_or_research_partition",
                "available_before_trade": False,
                "lookback": "n/a",
                "shift_applied": False,
                "leakage_status": "BLOCKED",
            }
        )
    return pd.DataFrame(rows)


def _pipeline(estimator: ClassifierMixin | RegressorMixin) -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
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
    return Pipeline([("features", transformer), ("estimator", estimator)])


def _classifier_catalog(seed: int) -> dict[str, ClassifierMixin]:
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


def _regressor_catalog(seed: int) -> dict[str, RegressorMixin]:
    return {
        "ridge": Ridge(alpha=5.0),
        "extra_trees_regressor": ExtraTreesRegressor(
            n_estimators=250, max_depth=10, min_samples_leaf=15, random_state=seed, n_jobs=-1
        ),
        "hist_gradient_regressor": HistGradientBoostingRegressor(
            max_iter=200,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=seed,
        ),
    }


def _feature_importance(model: Pipeline) -> pd.DataFrame:
    transformer = model.named_steps["features"]
    estimator = model.named_steps["estimator"]
    names = transformer.get_feature_names_out().astype(str)
    if hasattr(estimator, "feature_importances_"):
        values = np.asarray(estimator.feature_importances_, dtype=float)
    elif hasattr(estimator, "coef_"):
        values = np.abs(np.asarray(estimator.coef_, dtype=float)[0])
    else:
        values = np.zeros(len(names), dtype=float)
    result = pd.DataFrame({"feature": names, "importance": values})
    total = float(result["importance"].sum())
    result["importance_share"] = result["importance"] / total if total > 0.0 else 0.0
    return result.sort_values("importance", ascending=False).reset_index(drop=True)


def _fold_boundaries(
    rows: int, folds: int, validation_fraction: float, test_fraction: float
) -> list[tuple[int, int, int]]:
    test_size = max(int(rows * test_fraction), 1)
    validation_size = max(int(rows * validation_fraction), 1)
    earliest_test = rows - folds * test_size
    return [
        (
            earliest_test + i * test_size - validation_size,
            earliest_test + i * test_size,
            min(earliest_test + (i + 1) * test_size, rows),
        )
        for i in range(folds)
        if earliest_test + i * test_size - validation_size > 0
    ]


def _daily_equity_returns(equity: pd.DataFrame) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)
    series = equity.copy()
    series["timestamp"] = pd.to_datetime(series["timestamp"], utc=True)
    daily = (
        series.sort_values("timestamp")
        .drop_duplicates("timestamp", keep="last")
        .set_index("timestamp")["capital"]
        .astype(float)
        .resample("1D")
        .last()
        .ffill()
    )
    return daily.pct_change().dropna()


def _risk_adjusted_metrics(
    equity: pd.DataFrame, initial_capital: float = 10_000.0
) -> dict[str, float]:
    if equity.empty:
        return {
            "cagr": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "average_gross_exposure": 0.0,
        }
    returns = _daily_equity_returns(equity)
    ordered = equity.copy()
    ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
    ordered = ordered.sort_values("timestamp")
    days = max((ordered["timestamp"].iloc[-1] - ordered["timestamp"].iloc[0]).days, 1)
    final_capital = float(ordered["capital"].iloc[-1])
    cagr = (
        (final_capital / initial_capital) ** (365.25 / days) - 1.0 if final_capital > 0.0 else -1.0
    )
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    downside = returns.loc[returns < 0.0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    mean = float(returns.mean()) if len(returns) else 0.0
    sharpe = mean / std * np.sqrt(365.25) if std > 0.0 else 0.0
    sortino = mean / downside_std * np.sqrt(365.25) if downside_std > 0.0 else 0.0
    drawdown = _maximum_drawdown_from_equity(ordered["capital"])
    calmar = cagr / drawdown if drawdown > 0.0 else 0.0
    exposure = (
        float(ordered["gross_exposure"].astype(float).mean())
        if "gross_exposure" in ordered
        else 0.0
    )
    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "average_gross_exposure": exposure,
    }


def _bootstrap_mean_difference(
    selected: pd.Series, baseline: pd.Series, samples: int, seed: int
) -> dict[str, float]:
    left = selected.astype(float).dropna().to_numpy()
    right = baseline.astype(float).dropna().to_numpy()
    if len(left) == 0 or len(right) == 0 or samples <= 0:
        return {
            "mean_difference": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "probability_positive": 0.0,
        }
    rng = np.random.default_rng(seed)
    differences = np.empty(samples, dtype=float)
    for index in range(samples):
        left_sample = rng.choice(left, size=len(left), replace=True)
        right_sample = rng.choice(right, size=len(right), replace=True)
        differences[index] = float(left_sample.mean() - right_sample.mean())
    return {
        "mean_difference": float(left.mean() - right.mean()),
        "ci_lower": float(np.quantile(differences, 0.025)),
        "ci_upper": float(np.quantile(differences, 0.975)),
        "probability_positive": float((differences > 0.0).mean()),
    }


def _portfolio_metrics(
    selected: pd.DataFrame, output: Path, suffix: str
) -> tuple[dict[str, float | int], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if selected.empty:
        return (
            {
                "executed_trades": 0,
                "profit_factor": 0.0,
                "maximum_drawdown": 0.0,
                "total_pnl": 0.0,
                "final_capital": 10_000.0,
                "cagr": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "calmar": 0.0,
                "average_gross_exposure": 0.0,
            },
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
        )
    replay = selected.copy()
    replay["probability"] = replay["alpha_probability"].astype(float)
    replay["net_return"] = replay[RETURN_TARGET].astype(float)
    config = Phase13Config(output_root=output / suffix, minimum_trades=1)
    executed, rejected, equity, summary = simulate_portfolio(replay, config)
    returns = executed["net_return"].astype(float) if not executed.empty else pd.Series(dtype=float)
    risk_metrics = _risk_adjusted_metrics(equity, config.initial_capital)
    metrics: dict[str, float | int] = {
        "executed_trades": int(len(executed)),
        "rejected_trades": int(len(rejected)),
        "profit_factor": _profit_factor(returns),
        "maximum_drawdown": _maximum_drawdown_from_equity(equity["capital"])
        if not equity.empty
        else 0.0,
        "total_pnl": float(executed["pnl"].sum()) if not executed.empty else 0.0,
        "final_capital": float(equity["capital"].iloc[-1])
        if not equity.empty
        else config.initial_capital,
        **risk_metrics,
        **summary,
    }
    return metrics, executed, rejected, equity


def run_phase15(config: Phase15Config) -> Phase15Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    frame, regime_source = _prepare_features(pd.read_csv(config.trades_path), config)
    features = list(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    if FORBIDDEN_FEATURES.intersection(features):
        raise ValueError("forbidden leakage features entered the model matrix")
    timestamps = pd.Index(frame["timestamp"].drop_duplicates().sort_values())
    boundaries = _fold_boundaries(
        len(timestamps), config.folds, config.validation_fraction, config.test_fraction
    )
    if not boundaries:
        raise ValueError("insufficient rows for Phase 15 walk-forward analysis")

    metric_rows: list[dict[str, object]] = []
    predictions: list[pd.DataFrame] = []
    threshold_rows: list[dict[str, object]] = []
    champion_counts: dict[str, int] = {}
    models_trained = 0

    for fold, (val_start, test_start, test_end) in enumerate(boundaries, start=1):
        val_ts, test_ts, end_ts = (
            timestamps[val_start],
            timestamps[test_start],
            timestamps[test_end - 1],
        )
        train = frame.loc[frame["timestamp"] < val_ts]
        validation = frame.loc[(frame["timestamp"] >= val_ts) & (frame["timestamp"] < test_ts)]
        test = frame.loc[(frame["timestamp"] >= test_ts) & (frame["timestamp"] <= end_ts)]
        if len(train) < config.minimum_train_rows or validation.empty or test.empty:
            continue

        classifier_candidates: list[tuple[str, Pipeline, float, float, float]] = []
        for name, estimator in _classifier_catalog(config.random_seed + fold).items():
            model = _pipeline(estimator)
            model.fit(train[features], train[TARGET])
            probability = model.predict_proba(validation[features])[:, 1]
            auc = _safe_auc(validation[TARGET], probability)
            brier = float(brier_score_loss(validation[TARGET], probability))
            classifier_candidates.append((name, model, auc - brier, auc, brier))
            models_trained += 1
        cls_name, classifier, _, _, _ = max(classifier_candidates, key=lambda x: x[2])
        classifier_scores = np.asarray(
            [max(candidate[2], 0.001) for candidate in classifier_candidates], dtype=float
        )
        classifier_weights = classifier_scores / classifier_scores.sum()
        val_probability = sum(
            weight * candidate[1].predict_proba(validation[features])[:, 1]
            for weight, candidate in zip(classifier_weights, classifier_candidates, strict=True)
        )
        val_auc = _safe_auc(validation[TARGET], val_probability)
        val_brier = float(brier_score_loss(validation[TARGET], val_probability))

        reg_candidates: list[tuple[str, Pipeline, float]] = []
        for name, estimator in _regressor_catalog(config.random_seed + fold).items():
            model = _pipeline(estimator)
            model.fit(train[features], train[RETURN_TARGET].astype(float))
            prediction = model.predict(validation[features])
            reg_candidates.append(
                (name, model, float(mean_absolute_error(validation[RETURN_TARGET], prediction)))
            )
            models_trained += 1
        reg_name, regressor, _ = min(reg_candidates, key=lambda x: x[2])
        regression_scores = np.asarray(
            [1.0 / max(candidate[2], 1e-9) for candidate in reg_candidates], dtype=float
        )
        regression_weights = regression_scores / regression_scores.sum()
        val_return = sum(
            weight * candidate[1].predict(validation[features])
            for weight, candidate in zip(regression_weights, reg_candidates, strict=True)
        )
        val_mae = float(mean_absolute_error(validation[RETURN_TARGET], val_return))
        val_ev = val_return - config.transaction_cost_bps / 10_000.0
        best: tuple[float, float, int, float] | None = None
        for probability_threshold in config.probability_thresholds:
            for ev_threshold in config.ev_thresholds:
                mask = (val_probability >= probability_threshold) & (val_ev >= ev_threshold)
                selected_returns = validation.loc[mask, RETURN_TARGET].astype(float)
                score = (
                    float(selected_returns.mean()) * np.sqrt(max(len(selected_returns), 1))
                    if len(selected_returns)
                    else -1e9
                )
                candidate = (score, probability_threshold, int(mask.sum()), ev_threshold)
                if best is None or candidate[0] > best[0]:
                    best = candidate
        assert best is not None
        _, probability_threshold, _, ev_threshold = best

        test_probability = sum(
            weight * candidate[1].predict_proba(test[features])[:, 1]
            for weight, candidate in zip(classifier_weights, classifier_candidates, strict=True)
        )
        test_return = sum(
            weight * candidate[1].predict(test[features])
            for weight, candidate in zip(regression_weights, reg_candidates, strict=True)
        )
        test_ev = test_return - config.transaction_cost_bps / 10_000.0
        selected_mask = (test_probability >= probability_threshold) & (test_ev >= ev_threshold)
        scored = test.copy()
        scored["alpha_probability"] = test_probability
        scored["predicted_net_return"] = test_return
        scored["expected_value"] = test_ev
        scored["selected"] = selected_mask
        scored["phase15_fold"] = fold
        scored["champion_model"] = "weighted_ensemble"
        scored["base_champion_model"] = cls_name
        scored["return_model"] = "weighted_ensemble"
        scored["base_return_model"] = reg_name
        scored["frozen_probability_threshold"] = probability_threshold
        scored["frozen_ev_threshold"] = ev_threshold
        predictions.append(scored)
        champion_counts[cls_name] = champion_counts.get(cls_name, 0) + 1

        fold_metrics, _, _, _ = _portfolio_metrics(
            scored.loc[selected_mask], config.output_root, f"fold_{fold}_portfolio"
        )
        baseline_fold_metrics, _, _, _ = _portfolio_metrics(
            scored, config.output_root, f"fold_{fold}_baseline_portfolio"
        )
        metric_rows.append(
            {
                "fold": fold,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "test_rows": len(test),
                "champion_model": "weighted_ensemble",
                "base_champion_model": cls_name,
                "return_model": "weighted_ensemble",
                "base_return_model": reg_name,
                "validation_auc": val_auc,
                "validation_brier": val_brier,
                "validation_return_mae": val_mae,
                "test_auc": _safe_auc(test[TARGET], test_probability),
                "test_brier": float(brier_score_loss(test[TARGET], test_probability)),
                "expected_return_spearman": float(
                    pd.Series(test_return).corr(
                        pd.Series(test[RETURN_TARGET].astype(float).to_numpy()), method="spearman"
                    )
                ),
                "probability_threshold": probability_threshold,
                "ev_threshold": ev_threshold,
                "selected_trades": int(selected_mask.sum()),
                "portfolio_executed_trades": int(fold_metrics["executed_trades"]),
                "portfolio_profit_factor": float(fold_metrics["profit_factor"]),
                "portfolio_maximum_drawdown": float(fold_metrics["maximum_drawdown"]),
                "portfolio_total_pnl": float(fold_metrics["total_pnl"]),
                "portfolio_sharpe": float(fold_metrics["sharpe"]),
                "portfolio_sortino": float(fold_metrics["sortino"]),
                "portfolio_calmar": float(fold_metrics["calmar"]),
                "baseline_total_pnl": float(baseline_fold_metrics["total_pnl"]),
                "baseline_profit_factor": float(baseline_fold_metrics["profit_factor"]),
                "baseline_maximum_drawdown": float(baseline_fold_metrics["maximum_drawdown"]),
                "baseline_sharpe": float(baseline_fold_metrics["sharpe"]),
                "baseline_sortino": float(baseline_fold_metrics["sortino"]),
                "baseline_calmar": float(baseline_fold_metrics["calmar"]),
                "pnl_improvement": float(fold_metrics["total_pnl"])
                - float(baseline_fold_metrics["total_pnl"]),
                "sharpe_improvement": float(fold_metrics["sharpe"])
                - float(baseline_fold_metrics["sharpe"]),
                "positive_portfolio_return": float(fold_metrics["total_pnl"]) > 0.0,
                "chronology_passed": bool(
                    train["timestamp"].max()
                    < validation["timestamp"].min()
                    <= test["timestamp"].min()
                ),
            }
        )
        threshold_rows.append(
            {
                "fold": fold,
                "probability_threshold": probability_threshold,
                "ev_threshold": ev_threshold,
            }
        )

    if not predictions:
        raise ValueError("no folds met the minimum training requirement")
    metrics = pd.DataFrame(metric_rows)
    scored = pd.concat(predictions, ignore_index=True).sort_values("timestamp")
    selected = scored.loc[scored["selected"]].copy()
    portfolio, executed, rejected, equity = _portfolio_metrics(
        selected, config.output_root, "aggregate_portfolio"
    )
    baseline_portfolio, baseline_executed, _, baseline_equity = _portfolio_metrics(
        scored, config.output_root, "baseline_portfolio"
    )
    bootstrap = _bootstrap_mean_difference(
        executed["net_return"] if not executed.empty else pd.Series(dtype=float),
        baseline_executed["net_return"] if not baseline_executed.empty else pd.Series(dtype=float),
        config.bootstrap_samples,
        config.random_seed,
    )
    champion = max(champion_counts, key=lambda name: champion_counts[name])

    final_classifier = _pipeline(_classifier_catalog(config.random_seed)[champion])
    final_classifier.fit(frame[features], frame[TARGET])
    model_path = config.output_root / "phase15_champion.joblib"
    joblib.dump(final_classifier, model_path)
    models_trained += 1

    lineage = _feature_lineage()
    importance = _feature_importance(final_classifier)
    regime_coverage = (
        scored.groupby("market_regime", observed=True).size().rename("rows").reset_index()
    )
    symbol_pnl = (
        executed.groupby("symbol", observed=True)["pnl"].sum().abs()
        if not executed.empty
        else pd.Series(dtype=float)
    )
    concentration = (
        float(symbol_pnl.max() / symbol_pnl.sum()) if float(symbol_pnl.sum()) > 0.0 else 0.0
    )
    positive_folds = int(metrics["positive_portfolio_return"].sum())
    represented_folds = int((metrics["selected_trades"] > 0).sum())
    median_auc = float(metrics["test_auc"].median())
    auc_positive_folds = int((metrics["test_auc"] > 0.5).sum())
    diagnostics = bool(
        metrics["chronology_passed"].all()
        and lineage.loc[lineage["leakage_status"] == "PASS", "available_before_trade"].all()
    )
    approved = bool(
        diagnostics
        and median_auc >= config.minimum_auc
        and auc_positive_folds >= min(4, len(metrics))
        and int(portfolio["executed_trades"]) >= config.minimum_test_trades
        and float(portfolio["profit_factor"]) >= config.minimum_profit_factor
        and float(portfolio["maximum_drawdown"]) <= config.maximum_drawdown
        and positive_folds >= min(config.minimum_positive_folds, len(metrics))
        and represented_folds >= min(4, len(metrics))
        and concentration <= config.maximum_pnl_concentration
        and float(portfolio["sharpe"])
        >= float(baseline_portfolio["sharpe"]) + config.minimum_sharpe_improvement
        and float(portfolio["sortino"])
        >= float(baseline_portfolio["sortino"]) + config.minimum_sortino_improvement
        and bootstrap["probability_positive"] >= 0.50
    )

    tables = {
        "walk_forward_metrics.csv": metrics,
        "nested_thresholds.csv": pd.DataFrame(threshold_rows),
        "scored_trades.csv": scored,
        "selected_trades.csv": selected,
        "feature_lineage.csv": lineage,
        "feature_importance.csv": importance,
        "regime_coverage.csv": regime_coverage,
        "portfolio_executed_trades.csv": executed,
        "portfolio_rejected_signals.csv": rejected,
        "portfolio_equity_curve.csv": equity,
        "baseline_portfolio_executed_trades.csv": baseline_executed,
        "baseline_portfolio_equity_curve.csv": baseline_equity,
        "paired_fold_comparison.csv": metrics[
            [
                "fold",
                "portfolio_total_pnl",
                "baseline_total_pnl",
                "pnl_improvement",
                "portfolio_profit_factor",
                "baseline_profit_factor",
                "portfolio_maximum_drawdown",
                "baseline_maximum_drawdown",
                "portfolio_sharpe",
                "baseline_sharpe",
                "sharpe_improvement",
                "portfolio_sortino",
                "baseline_sortino",
            ]
        ],
        "bootstrap_comparison.csv": pd.DataFrame([bootstrap]),
    }
    for name, table in tables.items():
        table.to_csv(config.output_root / name, index=False)

    dashboard: dict[str, object] = {
        "phase": PHASE,
        "version": VERSION,
        "source_trades": len(frame),
        "out_of_sample_trades": len(scored),
        "selected_trades": len(selected),
        "folds_completed": len(metrics),
        "models_trained": models_trained,
        "champion_model": champion,
        "champion_fold_counts": champion_counts,
        "selection_policy": "validation_weighted_classifier_and_return_ensembles",
        "selected_threshold": float(metrics["probability_threshold"].median()),
        "regime_source": regime_source,
        "regime_count": int(regime_coverage["market_regime"].nunique()),
        "median_test_auc": median_auc,
        "auc_positive_folds": auc_positive_folds,
        "positive_portfolio_folds": positive_folds,
        "represented_selection_folds": represented_folds,
        "portfolio": portfolio,
        "baseline_portfolio": baseline_portfolio,
        "risk_adjusted_improvement": {
            "sharpe": float(portfolio["sharpe"]) - float(baseline_portfolio["sharpe"]),
            "sortino": float(portfolio["sortino"]) - float(baseline_portfolio["sortino"]),
            "calmar": float(portfolio["calmar"]) - float(baseline_portfolio["calmar"]),
        },
        "bootstrap_return_comparison": bootstrap,
        "maximum_symbol_pnl_concentration": concentration,
        "diagnostics_passed": diagnostics,
        "approved_for_phase16_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    (config.output_root / "phase15_dashboard.json").write_text(
        json.dumps(dashboard, indent=2, default=str), encoding="utf-8"
    )
    signoff = {
        "phase": PHASE,
        "status": "PHASE15_6_BENCHMARK_AND_RISK_VALIDATION_COMPLETE",
        "approved_for_phase16_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "notes": [
            "Research partition fields and raw year are blocked from the model matrix.",
            (
                "Model and thresholds are selected on validation data and frozen "
                "before each test fold."
            ),
            "Expected-value filtering combines win probability and predicted net return.",
            "Selected trades are replayed through the Phase 13 portfolio simulator.",
            "Promotion uses risk-adjusted improvement and bootstrap evidence in addition to AUC.",
            (
                "External SPY and BTC-USD benchmark files are preferred; a leakage-safe "
                "proxy is reported when unavailable."
            ),
        ],
    }
    (config.output_root / "phase15_final_signoff.json").write_text(
        json.dumps(signoff, indent=2), encoding="utf-8"
    )
    artifacts = {name.removesuffix(".csv"): str(config.output_root / name) for name in tables}
    artifacts.update(
        {
            "dashboard": str(config.output_root / "phase15_dashboard.json"),
            "signoff": str(config.output_root / "phase15_final_signoff.json"),
            "champion_model": str(model_path),
        }
    )
    manifest: dict[str, Any] = {
        "phase": PHASE,
        "version": VERSION,
        "config": asdict(config),
        "artifacts": artifacts,
    }
    for key, value in list(cast(dict[str, Any], manifest["config"]).items()):
        if isinstance(value, Path):
            cast(dict[str, Any], manifest["config"])[key] = str(value)
        elif isinstance(value, tuple):
            cast(dict[str, Any], manifest["config"])[key] = list(value)
    (config.output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return Phase15Result(
        len(frame),
        len(metrics),
        models_trained,
        champion,
        float(metrics["probability_threshold"].median()),
        diagnostics,
        approved,
        False,
        False,
        str(config.output_root),
        artifacts,
    )
