from src.backtest import BacktestConfig, BacktestEngine
from src.data.demo import make_demo_bars
from src.strategies.moving_average import MovingAverageCrossStrategy


def test_backtest_produces_equity_trades_and_metrics() -> None:
    bars = make_demo_bars(rows=120)
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    result = BacktestEngine().run(
        bars, strategy, BacktestConfig(initial_cash=10_000.0, slippage_bps=1.0)
    )
    assert len(result.equity_curve) == 120
    assert not result.trades.empty
    assert result.metrics["final_equity"] > 0
    assert result.trades.iloc[0]["timestamp"] == bars.iloc[20]["timestamp"]


def test_backtest_rejects_insufficient_history() -> None:
    bars = make_demo_bars(rows=10)
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    try:
        BacktestEngine().run(bars, strategy, BacktestConfig())
    except ValueError as exc:
        assert "requires at least" in str(exc)
    else:
        raise AssertionError("Expected insufficient-history error")
