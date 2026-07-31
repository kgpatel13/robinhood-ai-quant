from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from src.atlas_v18.models import PerformanceMetrics


def _max_drawdown(equity: Sequence[float]) -> float:
    peak = float(equity[0])
    maximum = 0.0
    for value in equity:
        peak = max(peak, float(value))
        maximum = max(maximum, (peak - float(value)) / peak if peak > 0 else 0.0)
    return maximum


class PerformanceAnalytics:
    def calculate(self, equity: Sequence[float]) -> PerformanceMetrics:
        values = tuple(float(value) for value in equity if float(value) > 0)
        if len(values) < 2:
            return PerformanceMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        returns = tuple(values[index] / values[index - 1] - 1.0 for index in range(1, len(values)))
        mean = sum(returns) / len(returns)
        variance = sum((item - mean) ** 2 for item in returns) / max(len(returns) - 1, 1)
        volatility = sqrt(variance) * sqrt(252.0)
        annualized_return = (values[-1] / values[0]) ** (252.0 / len(returns)) - 1.0
        sharpe = mean / sqrt(variance) * sqrt(252.0) if variance > 0 else 0.0
        downside = tuple(min(0.0, item) for item in returns)
        downside_variance = sum(item**2 for item in downside) / len(downside)
        sortino = mean / sqrt(downside_variance) * sqrt(252.0) if downside_variance > 0 else 0.0
        drawdown = _max_drawdown(values)
        gains = tuple(item for item in returns if item > 0)
        losses = tuple(item for item in returns if item < 0)
        gross_profit = sum(gains)
        gross_loss = abs(sum(losses))
        win_rate = len(gains) / len(returns)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        expectancy = mean
        return PerformanceMetrics(
            observations=len(returns),
            total_return=values[-1] / values[0] - 1.0,
            annualized_return=annualized_return,
            annualized_volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=drawdown,
            calmar_ratio=annualized_return / drawdown if drawdown > 0 else 0.0,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
        )
