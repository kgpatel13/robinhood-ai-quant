from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class TrainingConfig:
    model_type: str = "logistic_regression"
    splits: int = 5
    random_state: int = 42
    minimum_rows: int = 100

    def __post_init__(self) -> None:
        if self.model_type not in {"logistic_regression", "random_forest"}:
            raise ValueError(f"unsupported model_type: {self.model_type}")
        if self.splits < 2:
            raise ValueError("splits must be at least two")
        if self.minimum_rows < 20:
            raise ValueError("minimum_rows must be at least 20")


@dataclass(frozen=True)
class FoldMetric:
    fold: int
    train_rows: int
    validation_rows: int
    accuracy: float
    precision: float
    recall: float
    roc_auc: float


@dataclass(frozen=True)
class TrainingResult:
    model_name: str
    trained_at: datetime
    rows: int
    features: tuple[str, ...]
    folds: tuple[FoldMetric, ...]
    mean_accuracy: float
    mean_precision: float
    mean_recall: float
    mean_roc_auc: float
    feature_importance: dict[str, float]


class ProbabilityClassifier(Protocol):
    def fit(self, x: pd.DataFrame, y: pd.Series) -> Any: ...

    def predict(self, x: pd.DataFrame) -> np.ndarray[Any, Any]: ...

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray[Any, Any]: ...


class TimeSeriesModelTrainer:
    """Train classification models with expanding-window time-series validation."""

    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()

    def train(
        self, features: pd.DataFrame, target: pd.Series
    ) -> tuple[ClassifierMixin, TrainingResult]:
        x, y = self._prepare(features, target)
        if len(x) < self.config.minimum_rows:
            raise ValueError(
                f"at least {self.config.minimum_rows} complete rows are required; received {len(x)}"
            )
        splitter = TimeSeriesSplit(n_splits=self.config.splits)
        folds: list[FoldMetric] = []
        for fold_number, (train_index, validation_index) in enumerate(splitter.split(x), start=1):
            model = self._build_model()
            train_x = x.iloc[train_index]
            train_y = y.iloc[train_index]
            validation_x = x.iloc[validation_index]
            validation_y = y.iloc[validation_index]
            model.fit(train_x, train_y)
            predictions = model.predict(validation_x)
            probabilities = model.predict_proba(validation_x)[:, 1]
            folds.append(
                FoldMetric(
                    fold=fold_number,
                    train_rows=len(train_x),
                    validation_rows=len(validation_x),
                    accuracy=float(accuracy_score(validation_y, predictions)),
                    precision=float(precision_score(validation_y, predictions, zero_division=0)),
                    recall=float(recall_score(validation_y, predictions, zero_division=0)),
                    roc_auc=self._safe_auc(validation_y, probabilities),
                )
            )
        final_model = self._build_model()
        final_model.fit(x, y)
        result = TrainingResult(
            model_name=self.config.model_type,
            trained_at=datetime.now(UTC),
            rows=len(x),
            features=tuple(x.columns),
            folds=tuple(folds),
            mean_accuracy=float(np.mean([fold.accuracy for fold in folds])),
            mean_precision=float(np.mean([fold.precision for fold in folds])),
            mean_recall=float(np.mean([fold.recall for fold in folds])),
            mean_roc_auc=float(np.mean([fold.roc_auc for fold in folds])),
            feature_importance=self._feature_importance(final_model, tuple(x.columns)),
        )
        return final_model, result

    def _build_model(self) -> ClassifierMixin:
        if self.config.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=5,
                random_state=self.config.random_state,
                n_jobs=1,
            )
        return Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2_000,
                        class_weight="balanced",
                        random_state=self.config.random_state,
                    ),
                ),
            ]
        )

    @staticmethod
    def _prepare(features: pd.DataFrame, target: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        x = features.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        y = pd.to_numeric(target, errors="coerce").rename("target")
        joined = pd.concat([x, y], axis=1).dropna()
        clean_y = joined.pop("target").astype(int)
        if not set(clean_y.unique()).issubset({0, 1}):
            raise ValueError("target must contain binary values 0 and 1")
        if clean_y.nunique() < 2:
            raise ValueError("target must contain both classes")
        return joined.astype(float), clean_y

    @staticmethod
    def _safe_auc(target: pd.Series, probabilities: np.ndarray[Any, Any]) -> float:
        if target.nunique() < 2:
            return 0.5
        return float(roc_auc_score(target, probabilities))

    @staticmethod
    def _feature_importance(model: ClassifierMixin, names: tuple[str, ...]) -> dict[str, float]:
        raw: np.ndarray[Any, Any]
        if isinstance(model, Pipeline):
            estimator = model.named_steps["model"]
            raw = np.abs(np.asarray(estimator.coef_[0], dtype=float))
        else:
            raw = np.asarray(model.feature_importances_, dtype=float)
        total = float(raw.sum())
        normalized = raw / total if total > 0 else np.zeros_like(raw)
        ranked = sorted(zip(names, normalized, strict=True), key=lambda item: item[1], reverse=True)
        return {name: float(value) for name, value in ranked}


class ModelArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(self, model: ClassifierMixin, result: TrainingResult, version: str) -> Path:
        safe_version = version.strip().replace("/", "-").replace("\\", "-")
        if not safe_version:
            raise ValueError("version must not be empty")
        directory = self.root / result.model_name / safe_version
        directory.mkdir(parents=True, exist_ok=False)
        joblib.dump(model, directory / "model.joblib")
        metadata = asdict(result)
        metadata["trained_at"] = result.trained_at.isoformat()
        (directory / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        return directory

    def load(self, model_name: str, version: str) -> tuple[Any, dict[str, Any]]:
        directory = self.root / model_name / version
        model = joblib.load(directory / "model.joblib")
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        return model, metadata
