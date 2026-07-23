import pytest

from src.research.objectives import score_metrics


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sharpe", 1.5),
        ("cagr", 0.2),
        ("sortino", 2.0),
        ("calmar", 1.0),
        ("profit_factor", 1.8),
        ("max_drawdown", -0.2),
    ],
)
def test_objectives(name: str, expected: float) -> None:
    metrics = {
        "sharpe_ratio": 1.5,
        "cagr": 0.2,
        "sortino_ratio": 2.0,
        "max_drawdown": -0.2,
        "profit_factor": 1.8,
    }
    assert score_metrics(metrics, name) == pytest.approx(expected)
