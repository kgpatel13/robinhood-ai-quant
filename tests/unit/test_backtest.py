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


def test_backtest_records_costs_and_respects_exposure_cap() -> None:
    bars = make_demo_bars(rows=120)
    strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
    result = BacktestEngine().run(
        bars,
        strategy,
        BacktestConfig(
            initial_cash=10_000.0,
            slippage_bps=5.0,
            fee_bps=10.0,
            max_exposure=0.5,
        ),
    )
    assert result.metrics["total_costs"] > 0.0
    first_buy = result.trades[result.trades["side"] == "BUY"].iloc[0]
    entry_notional = float(first_buy["price"] * first_buy["quantity"])
    assert entry_notional <= 5_000.0
    assert "slippage_cost" in result.trades.columns


def test_backtest_rejects_invalid_exposure_cap() -> None:
    try:
        BacktestConfig(max_exposure=1.1)
    except ValueError as exc:
        assert "max_exposure" in str(exc)
    else:
        raise AssertionError("Expected invalid max_exposure error")
