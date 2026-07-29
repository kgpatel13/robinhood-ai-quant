from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray


@dataclass(frozen=True)
class WalkForwardConfig:
    minimum_train_rows: int = 100
    test_rows: int = 20
    step_rows: int = 20
    expanding: bool = True
    maximum_train_rows: int | None = None

    def __post_init__(self) -> None:
        if self.minimum_train_rows < 20:
            raise ValueError("minimum_train_rows must be at least 20")
        if self.test_rows < 1 or self.step_rows < 1:
            raise ValueError("test_rows and step_rows must be positive")
        if (
            self.maximum_train_rows is not None
            and self.maximum_train_rows < self.minimum_train_rows
        ):
            raise ValueError("maximum_train_rows cannot be below minimum_train_rows")


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    predictions: tuple[float, ...]
    target: tuple[int, ...]


@dataclass(frozen=True)
class WalkForwardResult:
    folds: tuple[WalkForwardFold, ...]
    predictions: tuple[float, ...]
    target: tuple[int, ...]
    coverage: float


class WalkForwardEvaluator[ModelT]:
    """Leakage-resistant chronological evaluation with expanding or rolling windows."""

    def __init__(self, config: WalkForwardConfig | None = None) -> None:
        self.config = config or WalkForwardConfig()

    def evaluate(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        *,
        fit: Callable[[pd.DataFrame, pd.Series], ModelT],
        predict_probability: Callable[[ModelT, pd.DataFrame], NDArray[np.float64]],
    ) -> WalkForwardResult:
        if len(features) != len(target):
            raise ValueError("features and target must have equal length")
        if len(features) < self.config.minimum_train_rows + self.config.test_rows:
            raise ValueError("insufficient rows for one walk-forward fold")
        folds: list[WalkForwardFold] = []
        all_predictions: list[float] = []
        all_targets: list[int] = []
        test_start = self.config.minimum_train_rows
        fold_number = 1
        while test_start < len(features):
            test_end = min(test_start + self.config.test_rows, len(features))
            if test_end <= test_start:
                break
            train_end = test_start
            train_start = 0
            if not self.config.expanding:
                window = self.config.maximum_train_rows or self.config.minimum_train_rows
                train_start = max(0, train_end - window)
            elif self.config.maximum_train_rows is not None:
                train_start = max(0, train_end - self.config.maximum_train_rows)
            train_x = features.iloc[train_start:train_end]
            train_y = target.iloc[train_start:train_end]
            test_x = features.iloc[test_start:test_end]
            test_y = target.iloc[test_start:test_end]
            model = fit(train_x, train_y)
            raw = np.asarray(predict_probability(model, test_x), dtype=float).reshape(-1)
            if len(raw) != len(test_x):
                raise ValueError("predict_probability returned an unexpected number of rows")
            predictions = tuple(float(value) for value in raw)
            targets = tuple(int(value) for value in test_y)
            folds.append(
                WalkForwardFold(
                    fold=fold_number,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    predictions=predictions,
                    target=targets,
                )
            )
            all_predictions.extend(predictions)
            all_targets.extend(targets)
            fold_number += 1
            test_start += self.config.step_rows
        unique_test_rows = len(
            {index for fold in folds for index in range(fold.test_start, fold.test_end)}
        )
        return WalkForwardResult(
            folds=tuple(folds),
            predictions=tuple(all_predictions),
            target=tuple(all_targets),
            coverage=unique_test_rows / len(features),
        )
