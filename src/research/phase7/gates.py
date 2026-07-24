from __future__ import annotations

from src.research.phase7.models import GateResult, PromotionGates


def _minimum(
    name: str,
    actual: float,
    threshold: float,
) -> GateResult:
    return GateResult(name, actual >= threshold, actual, threshold, ">=")


def evaluate_gates(
    metrics: dict[str, float | int | str | bool],
    gates: PromotionGates,
    score: float,
) -> tuple[GateResult, ...]:
    return (
        _minimum(
            "minimum_sharpe",
            float(metrics.get("oos_sharpe_ratio", 0.0)),
            gates.minimum_sharpe,
        ),
        _minimum(
            "positive_benchmark_alpha",
            float(metrics.get("oos_excess_cagr", 0.0)),
            gates.minimum_excess_cagr,
        ),
        _minimum(
            "maximum_drawdown",
            float(metrics.get("oos_max_drawdown", -1.0)),
            gates.maximum_drawdown,
        ),
        _minimum(
            "minimum_trades",
            float(metrics.get("completed_trades", 0)),
            float(gates.minimum_trades),
        ),
        _minimum(
            "parameter_stability",
            float(metrics.get("parameter_stability", 0.0)),
            gates.minimum_parameter_stability,
        ),
        _minimum(
            "cost_resilience",
            float(metrics.get("cost_resilience", 0.0)),
            gates.minimum_cost_resilience,
        ),
        _minimum(
            "cross_asset_consistency",
            float(metrics.get("cross_asset_consistency", 0.0)),
            gates.minimum_cross_asset_consistency,
        ),
        _minimum(
            "regime_score",
            float(metrics.get("regime_score", 0.0)),
            gates.minimum_regime_score,
        ),
        _minimum(
            "monte_carlo_survival",
            float(metrics.get("monte_carlo_survival", 0.0)),
            gates.minimum_monte_carlo_survival,
        ),
        _minimum("composite_score", score, gates.minimum_composite_score),
    )
