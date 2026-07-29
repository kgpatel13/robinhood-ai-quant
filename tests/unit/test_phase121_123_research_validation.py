import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.research_validation import (
    BootstrapConfig,
    CalibrationMethod,
    ProbabilityCalibrator,
    TradeReturnBootstrap,
    WalkForwardConfig,
    WalkForwardEvaluator,
)


def test_probability_calibrator_improves_brier_score() -> None:
    raw = np.array([0.05, 0.10, 0.20, 0.30, 0.70, 0.80, 0.90, 0.95] * 10)
    target = np.array([0, 0, 0, 1, 0, 1, 1, 1] * 10)
    calibrator = ProbabilityCalibrator(CalibrationMethod.ISOTONIC)
    calibrator.fit(raw, target)
    calibrated = calibrator.transform(raw)
    assert ProbabilityCalibrator.evaluate(calibrated, target).brier_score <= (
        ProbabilityCalibrator.evaluate(raw, target).brier_score
    )


def test_calibration_metrics_are_bounded() -> None:
    metrics = ProbabilityCalibrator.evaluate(
        np.array([0.1, 0.4, 0.6, 0.9]), np.array([0, 0, 1, 1]), bins=4
    )
    assert 0 <= metrics.expected_calibration_error <= 1
    assert metrics.observations == 4


def test_walk_forward_preserves_chronology() -> None:
    x = pd.DataFrame({"x": np.linspace(-2, 2, 140)})
    y = pd.Series((x["x"] > 0).astype(int))
    evaluator = WalkForwardEvaluator[LogisticRegression](
        WalkForwardConfig(minimum_train_rows=100, test_rows=10, step_rows=10)
    )
    result = evaluator.evaluate(
        x,
        y,
        fit=lambda train_x, train_y: LogisticRegression().fit(train_x, train_y),
        predict_probability=lambda model, test_x: model.predict_proba(test_x)[:, 1],
    )
    assert len(result.folds) == 4
    assert all(fold.train_end <= fold.test_start for fold in result.folds)
    assert len(result.predictions) == 40


def test_walk_forward_rolling_window_is_bounded() -> None:
    x = pd.DataFrame({"x": np.arange(150, dtype=float)})
    y = pd.Series([0, 1] * 75)
    evaluator = WalkForwardEvaluator[LogisticRegression](
        WalkForwardConfig(
            minimum_train_rows=60,
            test_rows=15,
            step_rows=15,
            expanding=False,
            maximum_train_rows=60,
        )
    )
    result = evaluator.evaluate(
        x,
        y,
        fit=lambda train_x, train_y: LogisticRegression().fit(train_x, train_y),
        predict_probability=lambda model, test_x: model.predict_proba(test_x)[:, 1],
    )
    assert all(fold.train_end - fold.train_start <= 60 for fold in result.folds)


def test_bootstrap_report_is_deterministic_and_profitable() -> None:
    returns = np.array([0.01, -0.004, 0.008, 0.003, -0.002] * 20)
    analyzer = TradeReturnBootstrap(BootstrapConfig(simulations=200, random_state=7))
    first = analyzer.analyze(returns)
    second = analyzer.analyze(returns)
    assert first == second
    assert first.probability_profitable > 0.9
    assert first.total_return_interval[0] < first.total_return_interval[1]
