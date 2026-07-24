from __future__ import annotations

from math import isfinite

from src.research.phase7.models import ScoreWeights


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if not isfinite(value):
        return low
    return max(low, min(high, value))


def composite_score(metrics: dict[str, float | int | str | bool], weights: ScoreWeights) -> float:
    total_return = float(metrics.get("oos_total_return", 0.0))
    sharpe = float(metrics.get("oos_sharpe_ratio", 0.0))
    drawdown = float(metrics.get("oos_max_drawdown", -1.0))
    excess = float(metrics.get("oos_excess_cagr", 0.0))
    trades = int(metrics.get("completed_trades", 0))
    stability = float(metrics.get("parameter_stability", 0.0))
    consistency = float(metrics.get("cross_asset_consistency", 0.0))
    regime = float(metrics.get("regime_score", 0.0))
    components = {
        "return_score": _clip(total_return / 1.0),
        "sharpe": _clip(sharpe / 1.5),
        "drawdown": _clip((drawdown + 0.60) / 0.60),
        "benchmark": _clip((excess + 0.10) / 0.20),
        "trades": _clip(trades / 50.0),
        "stability": _clip(stability),
        "consistency": _clip(consistency),
        "regime": _clip(regime),
    }
    score = sum(components[name] * weight for name, weight in vars(weights).items()) * 100.0
    return round(float(score), 4)
