from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.execution.models import AccountSnapshot
from src.execution.short_swing_provider import ShortSwingTargetProvider
from src.strategies import (
    AdaptiveMarketRegimeDetector,
    AdaptivePortfolioConstructor,
    DynamicSizingConfig,
    MLOpportunityRanker,
    OpportunityRankingConfig,
    OpportunityTrainingRow,
    ShortSwingCandidate,
)


def _candidate(symbol: str, score: float, quality: float = 0.8) -> ShortSwingCandidate:
    return ShortSwingCandidate(
        symbol=symbol,
        score=score,
        strategy_scores={
            "momentum": score,
            "breakout": score - 0.05,
            "pullback": score - 0.1,
            "quality": quality,
        },
        latest_price=100.0,
    )


def _bars(growth: float = 0.003) -> pd.DataFrame:
    close = [100.0 * (1 + growth) ** index for index in range(80)]
    return pd.DataFrame(
        {
            "close": close,
            "high": [value * 1.01 for value in close],
            "volume": [1_000_000.0] * 80,
        }
    )


def test_ranker_uses_deterministic_fallback_without_training() -> None:
    ranker = MLOpportunityRanker()
    ranked = ranker.rank((_candidate("AAPL", 0.8), _candidate("MSFT", 0.65)))
    assert [item.candidate.symbol for item in ranked] == ["AAPL", "MSFT"]
    assert all(item.source == "deterministic_fallback" for item in ranked)


def test_ranker_trains_and_blends_probability() -> None:
    ranker = MLOpportunityRanker(
        OpportunityRankingConfig(minimum_training_rows=10, minimum_positive_rows=3)
    )
    rows = []
    for index in range(20):
        value = index / 20
        rows.append(
            OpportunityTrainingRow(
                features={
                    "ensemble_score": value,
                    "momentum": value,
                    "breakout": value,
                    "pullback": value,
                    "quality": value,
                    "regime_confidence": 0.8,
                },
                profitable=index >= 10,
            )
        )
    assert ranker.fit(rows)
    ranked = ranker.rank((_candidate("AAPL", 0.85),))
    assert ranked[0].source == "ml_blended"
    assert 0 <= ranked[0].probability <= 1


def test_dynamic_sizing_respects_position_cap_and_cash() -> None:
    ranker = MLOpportunityRanker()
    ranked = ranker.rank(
        tuple(
            _candidate(symbol, score)
            for symbol, score in [("AAPL", 0.9), ("MSFT", 0.85), ("NVDA", 0.8), ("QQQ", 0.75)]
        )
    )
    constructor = AdaptivePortfolioConstructor(
        DynamicSizingConfig(max_positions=4, max_position_weight=0.25, base_cash_reserve=0.10)
    )
    weights = constructor.construct(ranked)
    assert sum(weights.values()) <= 0.90 + 1e-9
    assert max(weights.values()) <= 0.25 + 1e-9


def test_provider_v3_integrates_ranking_and_dynamic_sizing() -> None:
    bars = {symbol: _bars() for symbol in ("SPY", "AAPL", "MSFT", "NVDA")}
    provider = ShortSwingTargetProvider(
        lambda _: bars,
        regime_detector=AdaptiveMarketRegimeDetector(),
        opportunity_ranker=MLOpportunityRanker(),
        portfolio_constructor=AdaptivePortfolioConstructor(),
    )
    account = AccountSnapshot(cash=10_000.0, equity=10_000.0, buying_power=10_000.0, positions=())
    target = provider.generate(datetime.now(UTC), account)
    assert target.model_name == "short-swing-ensemble-v3-ml-adaptive"
    assert "ranking=" in target.details
    assert sum(target.weights.values()) <= 1.0


def test_provider_requires_ranker_and_constructor_together() -> None:
    try:
        ShortSwingTargetProvider(lambda _: {}, opportunity_ranker=MLOpportunityRanker())
    except ValueError as error:
        assert "configured together" in str(error)
    else:
        raise AssertionError("expected configuration error")
