from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MonteCarloResult:
    runs: int
    survival_probability: float
    median_return: float
    lower_return: float
    upper_return: float
    median_max_drawdown: float


def simulate_trade_returns(
    trade_returns: list[float], runs: int = 1000, seed: int = 42, confidence: float = 0.95
) -> MonteCarloResult:
    if not trade_returns:
        return MonteCarloResult(runs, 0.0, 0.0, 0.0, 0.0, -1.0)
    rng = np.random.default_rng(seed)
    values = np.asarray(trade_returns, dtype=float)
    totals: list[float] = []
    drawdowns: list[float] = []
    for _ in range(runs):
        sampled = rng.choice(values, size=len(values), replace=True)
        equity = np.cumprod(1.0 + sampled)
        totals.append(float(equity[-1] - 1.0))
        peaks = np.maximum.accumulate(equity)
        drawdowns.append(float(np.min(equity / peaks - 1.0)))
    alpha = (1.0 - confidence) / 2.0
    return MonteCarloResult(
        runs=runs,
        survival_probability=float(np.mean(np.asarray(totals) > 0.0)),
        median_return=float(np.median(totals)),
        lower_return=float(np.quantile(totals, alpha)),
        upper_return=float(np.quantile(totals, 1.0 - alpha)),
        median_max_drawdown=float(np.median(drawdowns)),
    )
