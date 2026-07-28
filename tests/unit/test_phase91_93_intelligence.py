from __future__ import annotations

import numpy as np
import pandas as pd

from src.intelligence import (
    MarketRegime,
    MarketRegimeClassifier,
    OptimizerConfig,
    PortfolioOptimizer,
    TechnicalFeatureEngineer,
    TimeSeriesModelTrainer,
    TrainingConfig,
)


def _bars(rows: int = 260) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    returns = rng.normal(0.0007, 0.012, rows)
    close = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": rng.integers(500_000, 2_000_000, rows),
        }
    )


def test_feature_engineer_produces_stable_named_features() -> None:
    engineered = TechnicalFeatureEngineer().transform(_bars())
    assert set(TechnicalFeatureEngineer.feature_names()) == set(engineered.columns)
    assert engineered.dropna().shape[0] > 150
    assert np.isfinite(engineered.dropna().to_numpy()).all()


def test_time_series_training_returns_cross_validation_metrics() -> None:
    bars = _bars(360)
    features = TechnicalFeatureEngineer().transform(bars)
    target = (bars["close"].shift(-5) > bars["close"]).astype(int)
    _, result = TimeSeriesModelTrainer(TrainingConfig(splits=3, minimum_rows=150)).train(
        features, target
    )
    assert len(result.folds) == 3
    assert result.rows >= 150
    assert 0.0 <= result.mean_accuracy <= 1.0
    assert set(result.feature_importance) == set(result.features)


def test_market_regime_classifier_returns_actionable_regime() -> None:
    bars = _bars()
    assessment = MarketRegimeClassifier().classify(bars)
    assert assessment.regime is not MarketRegime.INSUFFICIENT_DATA
    assert 0.0 <= assessment.confidence <= 1.0
    assert assessment.preferred_strategy_categories


def test_optimizer_respects_caps_and_cash_reserve() -> None:
    rng = np.random.default_rng(9)
    returns = pd.DataFrame(
        rng.normal(0.0005, [0.01, 0.015, 0.02, 0.012], size=(180, 4)),
        columns=["SPY", "QQQ", "AAPL", "MSFT"],
    )
    result = PortfolioOptimizer(
        OptimizerConfig(maximum_weight=0.30, cash_weight=0.10, target_portfolio_volatility=None)
    ).optimize(returns)
    assert max(result.weights.values()) <= 0.3000001
    assert abs(sum(result.weights.values()) + result.cash_weight - 1.0) < 1e-8
    assert result.estimated_volatility > 0.0
