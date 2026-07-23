from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scorecard:
    score: float
    status: str
    checks: dict[str, bool]


def build_scorecard(metrics: dict[str, float | int], minimum_trades: int = 20) -> Scorecard:
    checks = {
        "positive_oos_return": float(metrics.get("oos_total_return", 0.0)) > 0.0,
        "minimum_oos_sharpe": float(metrics.get("oos_sharpe_ratio", 0.0)) >= 0.75,
        "maximum_oos_drawdown": float(metrics.get("oos_max_drawdown", -1.0)) >= -0.25,
        "minimum_completed_trades": int(metrics.get("completed_trades", 0)) >= minimum_trades,
        "benchmark_improvement": (
            float(metrics.get("oos_excess_cagr", 0.0)) > 0.0
            or float(metrics.get("oos_max_drawdown", -1.0))
            > float(metrics.get("benchmark_max_drawdown", -1.0))
        ),
        "parameter_stability": float(metrics.get("parameter_stability", 0.0)) >= 0.60,
        "cost_resilience": float(metrics.get("cost_resilience", 0.0)) >= 0.70,
    }
    weights = {
        "positive_oos_return": 20.0,
        "minimum_oos_sharpe": 20.0,
        "maximum_oos_drawdown": 15.0,
        "minimum_completed_trades": 10.0,
        "benchmark_improvement": 15.0,
        "parameter_stability": 10.0,
        "cost_resilience": 10.0,
    }
    score = sum(weights[name] for name, passed in checks.items() if passed)
    if score >= 80.0 and all(checks.values()):
        status = "PAPER-TRADING ELIGIBLE"
    elif score >= 65.0:
        status = "CANDIDATE"
    elif score >= 40.0:
        status = "EXPERIMENTAL"
    else:
        status = "REJECTED"
    return Scorecard(score=score, status=status, checks=checks)
