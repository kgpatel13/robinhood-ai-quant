from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest import BacktestConfig, BacktestEngine
from src.research.benchmark import compare_to_benchmark
from src.research.engine import OptimizationEngine
from src.research.models import OptimizationConfig
from src.strategies import create_strategy


@dataclass(frozen=True)
class WalkForwardConfig:
    training_years: int = 5
    testing_years: int = 1
    step_years: int = 1
    minimum_test_rows: int = 100


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    parameters: dict[str, int | float]
    metrics: dict[str, float | int]


@dataclass(frozen=True)
class WalkForwardResult:
    windows: tuple[WalkForwardWindow, ...]
    equity_curve: pd.DataFrame
    metrics: dict[str, float | int]


class WalkForwardEngine:
    def run(
        self,
        bars: pd.DataFrame,
        optimization: OptimizationConfig,
        config: WalkForwardConfig,
    ) -> WalkForwardResult:
        ordered = bars.sort_values("timestamp").reset_index(drop=True)
        start = pd.Timestamp(ordered["timestamp"].iloc[0])
        end = pd.Timestamp(ordered["timestamp"].iloc[-1])
        test_start = start + pd.DateOffset(years=config.training_years)
        windows: list[WalkForwardWindow] = []
        curves: list[pd.DataFrame] = []
        capital = optimization.initial_cash
        completed_trades = 0
        while test_start < end:
            train_start = test_start - pd.DateOffset(years=config.training_years)
            train_end = test_start - pd.Timedelta(microseconds=1)
            test_end = min(test_start + pd.DateOffset(years=config.testing_years), end)
            train_mask = (ordered["timestamp"] >= train_start) & (ordered["timestamp"] <= train_end)
            test_mask = (ordered["timestamp"] >= test_start) & (ordered["timestamp"] <= test_end)
            train = ordered[train_mask]
            test = ordered[test_mask]
            if len(test) >= config.minimum_test_rows:
                optimized = OptimizationEngine().run(train, optimization)
                parameters = optimized.trials[0].parameters
                strategy = create_strategy(optimization.strategy, **parameters)
                bt_config = BacktestConfig(
                    initial_cash=capital,
                    commission_per_trade=optimization.commission_per_trade,
                    slippage_bps=optimization.slippage_bps,
                    fee_bps=optimization.fee_bps,
                )
                result = BacktestEngine().run(test, strategy, bt_config)
                metrics, _ = compare_to_benchmark(result.equity_curve, test, capital)
                metrics.update(result.metrics)
                metrics["completed_trades"] = int(result.metrics.get("trade_count", 0))
                completed_trades += int(metrics["completed_trades"])
                capital = float(result.equity_curve["equity"].iloc[-1])
                curve = result.equity_curve.copy()
                curve["window"] = len(windows) + 1
                curves.append(curve)
                windows.append(
                    WalkForwardWindow(
                        train_start=train_start,
                        train_end=train_end,
                        test_start=test_start,
                        test_end=test_end,
                        parameters=parameters,
                        metrics=metrics,
                    )
                )
            test_start += pd.DateOffset(years=config.step_years)
        if not windows:
            raise ValueError("Insufficient history for requested walk-forward configuration")
        equity = pd.concat(curves, ignore_index=True).drop_duplicates("timestamp", keep="last")
        returns = equity["equity"].pct_change().fillna(0.0)
        running_max = equity["equity"].cummax()
        total_return = float(equity["equity"].iloc[-1] / optimization.initial_cash - 1.0)
        metrics = {
            "window_count": len(windows),
            "completed_trades": completed_trades,
            "oos_total_return": total_return,
            "oos_sharpe_ratio": float(returns.mean() / returns.std(ddof=0) * (252.0**0.5))
            if returns.std(ddof=0)
            else 0.0,
            "oos_max_drawdown": float((equity["equity"] / running_max - 1.0).min()),
            "oos_excess_cagr": float(
                sum(float(item.metrics.get("excess_cagr", 0.0)) for item in windows) / len(windows)
            ),
            "benchmark_max_drawdown": float(
                min(float(item.metrics.get("benchmark_max_drawdown", 0.0)) for item in windows)
            ),
        }
        return WalkForwardResult(tuple(windows), equity, metrics)
