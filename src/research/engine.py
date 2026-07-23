from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import pandas as pd

from src.backtest import BacktestConfig, BacktestEngine
from src.research.models import OptimizationConfig, OptimizationResult, OptimizationTrial
from src.research.objectives import score_metrics
from src.research.search import generate_candidates
from src.strategies import create_strategy


def _evaluate_candidate(
    bars: pd.DataFrame,
    strategy_name: str,
    parameters: dict[str, int | float],
    backtest_config: BacktestConfig,
    objective: str,
) -> tuple[dict[str, int | float], float, dict[str, float | int], pd.DataFrame]:
    strategy = create_strategy(strategy_name, **parameters)
    result = BacktestEngine().run(bars, strategy, backtest_config)
    return parameters, score_metrics(result.metrics, objective), result.metrics, result.equity_curve


class OptimizationEngine:
    def run(self, bars: pd.DataFrame, config: OptimizationConfig) -> OptimizationResult:
        candidates = generate_candidates(config)
        if not candidates:
            raise ValueError("optimization generated no candidates")
        backtest_config = BacktestConfig(
            initial_cash=config.initial_cash,
            commission_per_trade=config.commission_per_trade,
            slippage_bps=config.slippage_bps,
        )
        raw: list[tuple[dict[str, int | float], float, dict[str, float | int], pd.DataFrame]]
        if config.workers == 1:
            raw = [
                _evaluate_candidate(
                    bars, config.strategy, parameters, backtest_config, config.objective
                )
                for parameters in candidates
            ]
        else:
            with ProcessPoolExecutor(max_workers=config.workers) as executor:
                futures = [
                    executor.submit(
                        _evaluate_candidate,
                        bars,
                        config.strategy,
                        parameters,
                        backtest_config,
                        config.objective,
                    )
                    for parameters in candidates
                ]
                raw = [future.result() for future in futures]
        raw.sort(key=lambda item: item[1], reverse=True)
        trials = tuple(
            OptimizationTrial(rank=index, parameters=item[0], score=item[1], metrics=item[2])
            for index, item in enumerate(raw, start=1)
        )
        return OptimizationResult(
            config=replace(config), trials=trials, best_equity_curve=raw[0][3]
        )
