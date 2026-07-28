import pandas as pd

from src.control_center import IntradayOpportunityRanker


def bars(multiplier: float = 1.0) -> pd.DataFrame:
    close = [100 + i * 0.1 * multiplier for i in range(40)]
    return pd.DataFrame({"close": close, "volume": [1000 + i * 20 for i in range(40)]})


def test_ranker_is_deterministic_and_sorted() -> None:
    result = IntradayOpportunityRanker().rank(
        {"BBB": bars(0.8), "AAA": bars(1.2)}, minimum_score=0.0, maximum_candidates=10
    )
    assert len(result) == 2
    assert result[0].score >= result[1].score


def test_ranker_honors_limit() -> None:
    result = IntradayOpportunityRanker().rank(
        {"AAA": bars(), "BBB": bars(), "CCC": bars()}, minimum_score=0.0, maximum_candidates=2
    )
    assert len(result) == 2
