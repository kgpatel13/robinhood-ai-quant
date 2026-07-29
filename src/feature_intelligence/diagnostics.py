from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.inspection import permutation_importance
from sklearn.metrics import mutual_info_score


@dataclass(frozen=True)
class FeatureScore:
    feature: str
    score: float


@dataclass(frozen=True)
class RedundantFeaturePair:
    left: str
    right: str
    correlation: float


@dataclass(frozen=True)
class FeatureDiagnosticReport:
    permutation_importance: tuple[FeatureScore, ...]
    information_coefficient: tuple[FeatureScore, ...]
    mutual_information: tuple[FeatureScore, ...]
    redundant_pairs: tuple[RedundantFeaturePair, ...]
    prune_candidates: tuple[str, ...]


class FeatureDiagnostics:
    def __init__(self, *, random_state: int = 42, correlation_threshold: float = 0.9) -> None:
        if not 0 < correlation_threshold <= 1:
            raise ValueError("correlation_threshold must be in (0, 1]")
        self.random_state = random_state
        self.correlation_threshold = correlation_threshold

    def analyze(
        self,
        *,
        model: object,
        features: pd.DataFrame,
        target: pd.Series,
        scorer: str | Callable[..., float] | None = None,
        repeats: int = 5,
    ) -> FeatureDiagnosticReport:
        self._validate(features, target, repeats)
        permutation = permutation_importance(
            model,
            features,
            target,
            scoring=scorer,
            n_repeats=repeats,
            random_state=self.random_state,
        )
        feature_names = [str(column) for column in features.columns]
        permutation_scores = self._rank(feature_names, permutation.importances_mean)
        ic_scores = self._rank(
            feature_names,
            np.asarray(
                [self._information_coefficient(features[column], target) for column in features]
            ),
        )
        mi_scores = self._rank(
            feature_names,
            np.asarray([self._mutual_information(features[column], target) for column in features]),
        )
        redundant = self._redundant_pairs(features)
        prune = self._prune_candidates(permutation_scores, redundant)
        return FeatureDiagnosticReport(permutation_scores, ic_scores, mi_scores, redundant, prune)

    @staticmethod
    def stability(
        feature_scores: Sequence[dict[str, float]], *, minimum_presence: float = 0.6
    ) -> dict[str, float]:
        if not feature_scores:
            return {}
        if not 0 < minimum_presence <= 1:
            raise ValueError("minimum_presence must be in (0, 1]")
        names = sorted({name for period in feature_scores for name in period})
        result: dict[str, float] = {}
        for name in names:
            values = [period[name] for period in feature_scores if name in period]
            if len(values) / len(feature_scores) >= minimum_presence:
                mean = float(np.mean(values))
                spread = float(np.std(values))
                result[name] = mean / (1.0 + spread)
        return result

    @staticmethod
    def _validate(features: pd.DataFrame, target: pd.Series, repeats: int) -> None:
        if features.empty:
            raise ValueError("features must not be empty")
        if len(features) != len(target):
            raise ValueError("features and target must have equal length")
        if repeats < 1:
            raise ValueError("repeats must be positive")
        if features.columns.duplicated().any():
            raise ValueError("feature names must be unique")

    @staticmethod
    def _rank(names: Sequence[str], values: NDArray[np.float64]) -> tuple[FeatureScore, ...]:
        items = [
            FeatureScore(str(name), float(value))
            for name, value in zip(names, values, strict=True)
        ]
        return tuple(sorted(items, key=lambda item: abs(item.score), reverse=True))

    @staticmethod
    def _information_coefficient(feature: pd.Series, target: pd.Series) -> float:
        joined = pd.concat([pd.to_numeric(feature, errors="coerce"), target], axis=1).dropna()
        if len(joined) < 3:
            return 0.0
        return float(joined.iloc[:, 0].corr(joined.iloc[:, 1], method="spearman"))

    @staticmethod
    def _mutual_information(feature: pd.Series, target: pd.Series) -> float:
        numeric = pd.to_numeric(feature, errors="coerce")
        valid = numeric.notna() & target.notna()
        if int(valid.sum()) < 5:
            return 0.0
        bins = min(10, max(2, int(np.sqrt(int(valid.sum())))))
        bucketed = pd.qcut(numeric[valid], q=bins, duplicates="drop")
        return float(mutual_info_score(bucketed.astype(str), target[valid]))

    def _redundant_pairs(self, features: pd.DataFrame) -> tuple[RedundantFeaturePair, ...]:
        correlation = features.corr(numeric_only=True).abs()
        pairs: list[RedundantFeaturePair] = []
        columns = list(correlation.columns)
        for index, left in enumerate(columns):
            for right in columns[index + 1 :]:
                value = float(cast(float, correlation.at[left, right]))
                if np.isfinite(value) and value >= self.correlation_threshold:
                    pairs.append(RedundantFeaturePair(left, right, value))
        return tuple(sorted(pairs, key=lambda item: item.correlation, reverse=True))

    @staticmethod
    def _prune_candidates(
        permutation_scores: tuple[FeatureScore, ...],
        redundant_pairs: tuple[RedundantFeaturePair, ...],
    ) -> tuple[str, ...]:
        score_map = {item.feature: abs(item.score) for item in permutation_scores}
        candidates: set[str] = {item.feature for item in permutation_scores if item.score <= 0}
        for pair in redundant_pairs:
            weaker = (
                pair.left
                if score_map.get(pair.left, 0.0) <= score_map.get(pair.right, 0.0)
                else pair.right
            )
            candidates.add(weaker)
        return tuple(sorted(candidates))
