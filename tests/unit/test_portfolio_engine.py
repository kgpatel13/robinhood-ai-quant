import pytest

from src.data.demo import make_demo_bars
from src.portfolio import PortfolioBacktestConfig, PortfolioBacktestEngine
from src.strategies.moving_average import MovingAverageCrossStrategy


def test_portfolio_engine_runs_multiple_assets() -> None:
    datasets = {
        "AAA": make_demo_bars("AAA", rows=120),
        "BBB": make_demo_bars("BBB", rows=120).assign(
            open=lambda frame: frame["open"] * 1.2,
            close=lambda frame: frame["close"] * 1.2,
        ),
    }
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    result = PortfolioBacktestEngine().run(
        datasets,
        strategy,
        PortfolioBacktestConfig(
            initial_cash=10_000,
            allocation_method="equal",
            rebalance_frequency="weekly",
            max_asset_weight=0.6,
        ),
    )
    assert len(result.equity_curve) == 120
    assert result.metrics["asset_count"] == 2
    assert result.metrics["final_equity"] > 0
    assert set(result.holdings["symbol"]) == {"AAA", "BBB"}
    assert not result.trades.empty


def test_portfolio_engine_requires_two_assets() -> None:
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    with pytest.raises(ValueError, match="at least two assets"):
        PortfolioBacktestEngine().run(
            {"AAA": make_demo_bars("AAA", rows=120)},
            strategy,
            PortfolioBacktestConfig(),
        )
