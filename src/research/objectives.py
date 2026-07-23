from __future__ import annotations

from collections.abc import Callable

MetricMap = dict[str, float | int]
Objective = Callable[[MetricMap], float]


def _metric(metrics: MetricMap, name: str) -> float:
    return float(metrics.get(name, 0.0))


def sharpe(metrics: MetricMap) -> float:
    return _metric(metrics, "sharpe_ratio")


def cagr(metrics: MetricMap) -> float:
    return _metric(metrics, "cagr")


def sortino(metrics: MetricMap) -> float:
    return _metric(metrics, "sortino_ratio")


def calmar(metrics: MetricMap) -> float:
    drawdown = abs(_metric(metrics, "max_drawdown"))
    return 0.0 if drawdown == 0.0 else _metric(metrics, "cagr") / drawdown


def profit_factor(metrics: MetricMap) -> float:
    return _metric(metrics, "profit_factor")


def max_drawdown(metrics: MetricMap) -> float:
    return _metric(metrics, "max_drawdown")


OBJECTIVES: dict[str, Objective] = {
    "sharpe": sharpe,
    "cagr": cagr,
    "sortino": sortino,
    "calmar": calmar,
    "profit_factor": profit_factor,
    "max_drawdown": max_drawdown,
}


def score_metrics(metrics: MetricMap, objective: str) -> float:
    try:
        return OBJECTIVES[objective](metrics)
    except KeyError as exc:
        raise ValueError(f"Unknown objective: {objective}") from exc
