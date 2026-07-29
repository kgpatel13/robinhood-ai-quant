from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin

from src.intelligence.modeling import TimeSeriesModelTrainer, TrainingConfig, TrainingResult
from src.ml_platform.registry import ModelRegistry, ModelStage, RegisteredModel


@dataclass(frozen=True)
class DriftReport:
    score: float
    drifted_features: tuple[str, ...]
    feature_scores: dict[str, float]
    threshold: float

    @property
    def drift_detected(self) -> bool:
        return bool(self.drifted_features)


class PopulationStabilityDriftDetector:
    def __init__(self, bins: int = 10, threshold: float = 0.2) -> None:
        if bins < 2:
            raise ValueError("bins must be at least two")
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        self.bins = bins
        self.threshold = threshold

    def compare(self, reference: pd.DataFrame, current: pd.DataFrame) -> DriftReport:
        shared = [column for column in reference.columns if column in current.columns]
        scores = {column: self._psi(reference[column], current[column]) for column in shared}
        drifted = tuple(
            sorted(column for column, score in scores.items() if score >= self.threshold)
        )
        overall = float(np.mean(list(scores.values()))) if scores else 0.0
        return DriftReport(overall, drifted, scores, self.threshold)

    def _psi(self, reference: pd.Series, current: pd.Series) -> float:
        ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy(dtype=float)
        cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy(dtype=float)
        if len(ref) < self.bins or len(cur) < self.bins:
            return 0.0
        boundaries = np.unique(np.quantile(ref, np.linspace(0, 1, self.bins + 1)))
        if len(boundaries) < 3:
            return 0.0
        boundaries[0] = -np.inf
        boundaries[-1] = np.inf
        ref_counts, _ = np.histogram(ref, bins=boundaries)
        cur_counts, _ = np.histogram(cur, bins=boundaries)
        epsilon = 1e-6
        ref_pct = np.maximum(ref_counts / max(ref_counts.sum(), 1), epsilon)
        cur_pct = np.maximum(cur_counts / max(cur_counts.sum(), 1), epsilon)
        return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


@dataclass(frozen=True)
class PromotionPolicy:
    metric: str = "mean_roc_auc"
    minimum_score: float = 0.55
    minimum_improvement: float = 0.01

    def should_promote(
        self, candidate_metrics: dict[str, float], champion_metrics: dict[str, float] | None
    ) -> bool:
        candidate = candidate_metrics.get(self.metric, float("-inf"))
        if candidate < self.minimum_score:
            return False
        if champion_metrics is None:
            return True
        champion = champion_metrics.get(self.metric, float("-inf"))
        return candidate >= champion + self.minimum_improvement


@dataclass(frozen=True)
class TrainingRun:
    run_id: str
    selected_config: TrainingConfig
    result: TrainingResult
    registered_model: RegisteredModel
    promoted: bool
    drift: DriftReport | None


class AutomatedTrainingPipeline:
    """Deterministic hyperparameter search, registration, and promotion workflow."""

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        promotion_policy: PromotionPolicy | None = None,
        drift_detector: PopulationStabilityDriftDetector | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.registry = registry
        self.promotion_policy = promotion_policy or PromotionPolicy()
        self.drift_detector = drift_detector or PopulationStabilityDriftDetector()
        self.clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        *,
        model_name: str,
        feature_set: str,
        features: pd.DataFrame,
        target: pd.Series,
        search_space: dict[str, tuple[Any, ...]] | None = None,
        reference_features: pd.DataFrame | None = None,
    ) -> TrainingRun:
        configurations = self._configurations(search_space)
        trained: list[tuple[ClassifierMixin, TrainingResult, TrainingConfig]] = []
        for config in configurations:
            model, result = TimeSeriesModelTrainer(config).train(features, target)
            trained.append((model, result, config))
        model, result, selected = max(trained, key=lambda item: item[1].mean_roc_auc)
        created = self.clock()
        run_id = created.strftime("%Y%m%dT%H%M%S%fZ")
        metrics = self._metrics(result)
        registered = self.registry.register(
            name=model_name,
            version=run_id,
            model=model,
            metrics=metrics,
            feature_set=feature_set,
            stage=ModelStage.CHALLENGER,
            metadata={"training_config": selected.__dict__},
        )
        champion = self.registry.champion(model_name)
        promote = self.promotion_policy.should_promote(
            metrics, champion.metrics if champion is not None else None
        )
        if promote:
            registered = self.registry.promote(model_name, run_id)
        drift = (
            self.drift_detector.compare(reference_features, features)
            if reference_features is not None
            else None
        )
        return TrainingRun(run_id, selected, result, registered, promote, drift)

    @staticmethod
    def _configurations(
        search_space: dict[str, tuple[Any, ...]] | None,
    ) -> tuple[TrainingConfig, ...]:
        if not search_space:
            return (TrainingConfig(),)
        allowed = {"model_type", "splits", "random_state", "minimum_rows"}
        unknown = set(search_space) - allowed
        if unknown:
            raise ValueError(f"unsupported training parameters: {sorted(unknown)}")
        defaults = TrainingConfig()
        keys = tuple(search_space)
        values = tuple(search_space[key] for key in keys)
        configs: list[TrainingConfig] = []
        for combination in product(*values):
            arguments = {
                "model_type": defaults.model_type,
                "splits": defaults.splits,
                "random_state": defaults.random_state,
                "minimum_rows": defaults.minimum_rows,
            }
            arguments.update(dict(zip(keys, combination, strict=True)))
            model_type = arguments["model_type"]
            splits = arguments["splits"]
            random_state = arguments["random_state"]
            minimum_rows = arguments["minimum_rows"]

            if not isinstance(model_type, str):
                raise TypeError("model_type must be a string")
            if not isinstance(splits, int) or isinstance(splits, bool):
                raise TypeError("splits must be an integer")
            if not isinstance(random_state, int) or isinstance(random_state, bool):
                raise TypeError("random_state must be an integer")
            if not isinstance(minimum_rows, int) or isinstance(minimum_rows, bool):
                raise TypeError("minimum_rows must be an integer")

            configs.append(
                TrainingConfig(
                    model_type=model_type,
                    splits=splits,
                    random_state=random_state,
                    minimum_rows=minimum_rows,
                )
            )
        return tuple(configs)

    @staticmethod
    def _metrics(result: TrainingResult) -> dict[str, float]:
        return {
            "mean_accuracy": result.mean_accuracy,
            "mean_precision": result.mean_precision,
            "mean_recall": result.mean_recall,
            "mean_roc_auc": result.mean_roc_auc,
        }
