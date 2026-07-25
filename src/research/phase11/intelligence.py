from __future__ import annotations

import math
from collections.abc import Iterable
from typing import cast

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from src.research.phase11.features import FEATURE_COLUMNS
from src.research.phase11.intelligence_models import FeatureIntelligenceConfig


def deterministic_sample(frame: pd.DataFrame, maximum_rows: int) -> pd.DataFrame:
    if len(frame) <= maximum_rows:
        return frame.copy()
    positions = np.linspace(0, len(frame) - 1, num=maximum_rows, dtype=int)
    return frame.iloc[positions].copy()


def feature_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total = max(len(frame), 1)
    for feature in FEATURE_COLUMNS:
        values = pd.to_numeric(frame[feature], errors="coerce")
        finite = values.replace([np.inf, -np.inf], np.nan).dropna()
        unique_count = int(finite.nunique())
        rows.append(
            {
                "feature": feature,
                "rows": len(frame),
                "missing_count": int(values.isna().sum()),
                "missing_fraction": float(values.isna().mean()),
                "infinite_count": int(
                    np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).sum()
                ),
                "unique_count": unique_count,
                "unique_fraction": unique_count / total,
                "mean": float(finite.mean()) if not finite.empty else math.nan,
                "standard_deviation": float(finite.std()) if len(finite) > 1 else 0.0,
                "minimum": float(finite.min()) if not finite.empty else math.nan,
                "p01": float(finite.quantile(0.01)) if not finite.empty else math.nan,
                "p25": float(finite.quantile(0.25)) if not finite.empty else math.nan,
                "median": float(finite.median()) if not finite.empty else math.nan,
                "p75": float(finite.quantile(0.75)) if not finite.empty else math.nan,
                "p99": float(finite.quantile(0.99)) if not finite.empty else math.nan,
                "maximum": float(finite.max()) if not finite.empty else math.nan,
                "skewness": cast(float, finite.skew()) if len(finite) > 2 else math.nan,
                "kurtosis": cast(float, finite.kurt()) if len(finite) > 3 else math.nan,
            }
        )
    return pd.DataFrame(rows)


def feature_outliers(frame: pd.DataFrame, z_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for feature in FEATURE_COLUMNS:
        values = pd.to_numeric(frame[feature], errors="coerce").replace([np.inf, -np.inf], np.nan)
        median = float(values.median())
        mad = float((values - median).abs().median())
        if not np.isfinite(mad) or mad == 0.0:
            outlier = pd.Series(False, index=values.index)
        else:
            robust_z = 0.67448975 * (values - median).abs() / mad
            outlier = robust_z > z_threshold
        rows.append(
            {
                "feature": feature,
                "outlier_count": int(outlier.sum()),
                "outlier_fraction": float(outlier.mean()),
                "robust_median": median,
                "median_absolute_deviation": mad,
                "z_threshold": z_threshold,
            }
        )
    return pd.DataFrame(rows)


def correlation_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame[list(FEATURE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    matrix = numeric.corr(method="spearman")
    matrix.index.name = "feature"
    result: pd.DataFrame = matrix.reset_index()
    return result


def feature_redundancy(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    numeric = frame[list(FEATURE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    matrix = numeric.corr(method="spearman")
    rows: list[dict[str, object]] = []
    for left_index, left in enumerate(FEATURE_COLUMNS):
        for right in FEATURE_COLUMNS[left_index + 1 :]:
            value = float(matrix.loc[left, right])
            if np.isfinite(value) and abs(value) >= threshold:
                rows.append(
                    {
                        "feature_a": left,
                        "feature_b": right,
                        "spearman_correlation": value,
                        "absolute_correlation": abs(value),
                        "threshold": threshold,
                    }
                )
    return pd.DataFrame(
        rows,
        columns=[
            "feature_a",
            "feature_b",
            "spearman_correlation",
            "absolute_correlation",
            "threshold",
        ],
    ).sort_values("absolute_correlation", ascending=False, ignore_index=True)


def feature_predictiveness(
    frame: pd.DataFrame,
    target_column: str,
    classification_target: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    target = pd.to_numeric(frame[target_column], errors="coerce")
    binary = pd.to_numeric(frame[classification_target], errors="coerce")
    for feature in FEATURE_COLUMNS:
        values = pd.to_numeric(frame[feature], errors="coerce")
        pair = pd.DataFrame({"feature": values, "target": target, "binary": binary}).dropna()
        if len(pair) < 20 or pair["feature"].nunique() < 2:
            rows.append(_empty_predictiveness(feature, len(pair)))
            continue
        pearson = float(pair["feature"].corr(pair["target"], method="pearson"))
        spearman = float(pair["feature"].corr(pair["target"], method="spearman"))
        mutual_information = _mutual_information(pair["feature"], pair["binary"])
        spread, monotonicity = _quantile_relationship(pair)
        rows.append(
            {
                "feature": feature,
                "observations": len(pair),
                "pearson_target": pearson,
                "spearman_target": spearman,
                "absolute_spearman": abs(spearman),
                "mutual_information_binary": mutual_information,
                "top_minus_bottom_quantile_return": spread,
                "quantile_monotonicity": monotonicity,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["absolute_spearman", "mutual_information_binary"],
        ascending=False,
        ignore_index=True,
    )


def _empty_predictiveness(feature: str, observations: int) -> dict[str, object]:
    return {
        "feature": feature,
        "observations": observations,
        "pearson_target": math.nan,
        "spearman_target": math.nan,
        "absolute_spearman": math.nan,
        "mutual_information_binary": math.nan,
        "top_minus_bottom_quantile_return": math.nan,
        "quantile_monotonicity": math.nan,
    }


def _mutual_information(values: pd.Series, target: pd.Series) -> float:
    try:
        bins = pd.qcut(values, q=min(10, values.nunique()), duplicates="drop")
    except ValueError:
        return 0.0
    table = pd.crosstab(bins, target, normalize=True)
    if table.empty:
        return 0.0
    row_probability = table.sum(axis=1)
    column_probability = table.sum(axis=0)
    information = 0.0
    for row in table.index:
        for column in table.columns:
            joint = float(table.loc[row, column])
            expected = float(row_probability.loc[row] * column_probability.loc[column])
            if joint > 0.0 and expected > 0.0:
                information += joint * math.log(joint / expected)
    return information


def _quantile_relationship(pair: pd.DataFrame) -> tuple[float, float]:
    try:
        quantiles = pd.qcut(pair["feature"], q=5, duplicates="drop")
    except ValueError:
        return math.nan, math.nan
    means = pair.groupby(quantiles, observed=True)["target"].mean()
    if len(means) < 2:
        return math.nan, math.nan
    spread = float(means.iloc[-1] - means.iloc[0])
    order = pd.Series(range(len(means)), dtype=float)
    monotonicity = float(pd.Series(means.to_numpy()).corr(order, method="spearman"))
    return spread, monotonicity


def feature_drift(frame: pd.DataFrame) -> pd.DataFrame:
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    years = sorted(int(value) for value in timestamps.dt.year.unique())
    rows: list[dict[str, object]] = []
    if len(years) < 2:
        return pd.DataFrame(
            columns=[
                "feature",
                "reference_year",
                "comparison_year",
                "ks_statistic",
                "p_value",
                "median_shift_iqr",
                "drift_score",
            ]
        )
    reference_year = years[0]
    for feature in FEATURE_COLUMNS:
        reference = _finite_values(frame.loc[timestamps.dt.year == reference_year, feature])
        if len(reference) < 20:
            continue
        reference_iqr = float(reference.quantile(0.75) - reference.quantile(0.25))
        scale = reference_iqr if reference_iqr > 0.0 else max(abs(float(reference.median())), 1e-12)
        for year in years[1:]:
            comparison = _finite_values(frame.loc[timestamps.dt.year == year, feature])
            if len(comparison) < 20:
                continue
            result = ks_2samp(reference, comparison, method="auto")
            median_shift = abs(float(comparison.median() - reference.median())) / scale
            drift_score = max(float(result.statistic), median_shift)
            rows.append(
                {
                    "feature": feature,
                    "reference_year": reference_year,
                    "comparison_year": year,
                    "ks_statistic": float(result.statistic),
                    "p_value": float(result.pvalue),
                    "median_shift_iqr": median_shift,
                    "drift_score": drift_score,
                }
            )
    return pd.DataFrame(rows)


def feature_stability(frame: pd.DataFrame, target_column: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_columns = ["asset_class", "holding_period"]
    for feature in FEATURE_COLUMNS:
        correlations: list[float] = []
        for _, group in frame.groupby(group_columns, observed=True):
            values = pd.to_numeric(group[feature], errors="coerce")
            target = pd.to_numeric(group[target_column], errors="coerce")
            pair = pd.DataFrame({"feature": values, "target": target}).dropna()
            if len(pair) < 30 or pair["feature"].nunique() < 2:
                continue
            correlation = float(pair["feature"].corr(pair["target"], method="spearman"))
            if np.isfinite(correlation):
                correlations.append(correlation)
        nonzero = [value for value in correlations if abs(value) >= 0.005]
        dominant_sign = 0
        if nonzero:
            dominant_sign = 1 if sum(value > 0 for value in nonzero) >= len(nonzero) / 2 else -1
        stable = [value for value in nonzero if int(math.copysign(1, value)) == dominant_sign]
        rows.append(
            {
                "feature": feature,
                "evaluated_groups": len(correlations),
                "nontrivial_groups": len(nonzero),
                "stable_sign_groups": len(stable),
                "stable_sign_fraction": len(stable) / len(nonzero) if nonzero else 0.0,
                "median_spearman": float(np.median(correlations)) if correlations else math.nan,
                "median_absolute_spearman": (
                    float(np.median(np.abs(correlations))) if correlations else math.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def coverage_report(frame: pd.DataFrame) -> pd.DataFrame:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    copy = frame.assign(year=timestamp.dt.year)
    rows: list[dict[str, object]] = []
    for dimension in ("asset_class", "symbol", "holding_period", "regime", "year"):
        counts = copy.groupby(dimension, observed=True).size()
        for value, count in counts.items():
            rows.append(
                {
                    "dimension": dimension,
                    "value": str(value),
                    "rows": int(count),
                    "fraction": float(count / len(copy)),
                }
            )
    return pd.DataFrame(rows)


def leakage_diagnostics(
    summary: pd.DataFrame,
    predictiveness: pd.DataFrame,
    suspicious_correlation: float,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    infinite = int(summary["infinite_count"].sum())
    missing = int(summary["missing_count"].sum())
    constant = int((summary["unique_count"] <= 1).sum())
    suspicious = int((predictiveness["absolute_spearman"] >= suspicious_correlation).sum())
    checks.extend(
        [
            _diagnostic("no_infinite_features", infinite == 0, infinite),
            _diagnostic("no_missing_features", missing == 0, missing),
            _diagnostic("no_constant_features", constant == 0, constant),
            _diagnostic(
                "no_suspicious_target_correlation",
                suspicious == 0,
                suspicious,
                f"absolute Spearman below {suspicious_correlation:.2f}",
            ),
        ]
    )
    return pd.DataFrame(checks)


def feature_recommendations(
    summary: pd.DataFrame,
    outliers: pd.DataFrame,
    predictiveness: pd.DataFrame,
    stability: pd.DataFrame,
    drift: pd.DataFrame,
    redundancy: pd.DataFrame,
    config: FeatureIntelligenceConfig,
) -> pd.DataFrame:
    maximum_drift = (
        drift.groupby("feature", observed=True)["drift_score"].max()
        if not drift.empty
        else pd.Series(dtype=float)
    )
    redundant_features = set(redundancy["feature_b"]) if not redundancy.empty else set()
    joined = (
        summary.merge(outliers, on="feature", how="left")
        .merge(predictiveness, on="feature", how="left")
        .merge(stability, on="feature", how="left")
    )
    rows: list[dict[str, object]] = []
    for record in joined.to_dict(orient="records"):
        feature = str(record["feature"])
        issues: list[str] = []
        action = "KEEP"
        unique_fraction = float(record["unique_fraction"])
        missing_fraction = float(record["missing_fraction"])
        outlier_fraction = float(record.get("outlier_fraction", 0.0))
        stable_fraction = float(record.get("stable_sign_fraction", 0.0))
        drift_score = float(maximum_drift.get(feature, 0.0))
        if int(record["unique_count"]) <= 1:
            action = "REMOVE"
            issues.append("constant")
        elif unique_fraction <= config.near_constant_unique_fraction:
            action = "REMOVE"
            issues.append("near_constant")
        if missing_fraction > 0.0:
            action = "REVIEW" if action == "KEEP" else action
            issues.append("missing_values")
        if feature in redundant_features and action == "KEEP":
            action = "REVIEW"
            issues.append("high_redundancy")
        if outlier_fraction > 0.01 and action == "KEEP":
            action = "KEEP_WITH_WINSORIZATION"
            issues.append("heavy_outliers")
        if drift_score >= config.drift_threshold and action.startswith("KEEP"):
            action = "REVIEW"
            issues.append("temporal_drift")
        if stable_fraction < config.minimum_stable_group_fraction and action == "KEEP":
            action = "REVIEW"
            issues.append("unstable_target_relationship")
        rows.append(
            {
                "feature": feature,
                "recommendation": action,
                "issues": "|".join(issues) if issues else "none",
                "missing_fraction": missing_fraction,
                "unique_fraction": unique_fraction,
                "outlier_fraction": outlier_fraction,
                "maximum_drift_score": drift_score,
                "absolute_spearman": float(record.get("absolute_spearman", math.nan)),
                "mutual_information_binary": float(
                    record.get("mutual_information_binary", math.nan)
                ),
                "stable_sign_fraction": stable_fraction,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["recommendation", "absolute_spearman"],
        ascending=[True, False],
        ignore_index=True,
    )


def _finite_values(values: Iterable[object]) -> pd.Series:
    series = pd.to_numeric(pd.Series(values), errors="coerce")
    return series.replace([np.inf, -np.inf], np.nan).dropna()


def _diagnostic(
    check: str,
    passed: bool,
    violations: int,
    detail: str = "",
) -> dict[str, object]:
    return {
        "check": check,
        "passed": passed,
        "violations": violations,
        "detail": detail,
    }
