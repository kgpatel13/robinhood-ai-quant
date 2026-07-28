from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.research_lab.backtest import StrategyBacktestEngine
from src.research_lab.models import StrategyBacktestResult
from src.strategies.registry import create_strategy


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    result: StrategyBacktestResult


class WalkForwardEngine:
    def __init__(self, backtester: StrategyBacktestEngine | None = None) -> None:
        self.backtester = backtester or StrategyBacktestEngine()

    def run(
        self, bars: pd.DataFrame, strategy_name: str, *, train_size: int = 252, test_size: int = 63
    ) -> tuple[WalkForwardFold, ...]:
        if train_size < 20 or test_size < 5:
            raise ValueError("train_size must be >= 20 and test_size >= 5")
        folds: list[WalkForwardFold] = []
        start = 0
        fold = 1
        while start + train_size + test_size <= len(bars):
            train = bars.iloc[start : start + train_size]
            test = bars.iloc[start + train_size : start + train_size + test_size]
            result = self.backtester.run(test, create_strategy(strategy_name))
            folds.append(
                WalkForwardFold(
                    fold,
                    pd.Timestamp(train.index[0]),
                    pd.Timestamp(train.index[-1]),
                    pd.Timestamp(test.index[0]),
                    pd.Timestamp(test.index[-1]),
                    result,
                )
            )
            fold += 1
            start += test_size
        return tuple(folds)
