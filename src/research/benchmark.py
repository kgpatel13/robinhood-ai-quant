from __future__ import annotations

import math

import pandas as pd


def _annualized_metrics(equity: pd.Series, timestamps: pd.Series) -> dict[str, float]:
    returns = equity.astype(float).pct_change().fillna(0.0)
    days = max((timestamps.iloc[-1] - timestamps.iloc[0]).days, 1)
    years = max(days / 365.25, 1 / 365.25)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)
    volatility = float(returns.std(ddof=0) * math.sqrt(252.0))
    deviation = float(returns.std(ddof=0))
    sharpe = 0.0 if deviation == 0.0 else float(returns.mean() / deviation * math.sqrt(252.0))
    running_max = equity.cummax()
    max_drawdown = float((equity / running_max - 1.0).min())
    calmar = 0.0 if max_drawdown == 0.0 else float(cagr / abs(max_drawdown))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar,
    }


def buy_and_hold_curve(bars: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    ordered = bars.sort_values("timestamp").reset_index(drop=True)
    first_open = float(ordered["open"].iloc[0])
    quantity = initial_cash / first_open
    return pd.DataFrame(
        {
            "timestamp": ordered["timestamp"],
            "equity": quantity * ordered["adjusted_close"].astype(float),
        }
    )


def compare_to_benchmark(
    strategy_curve: pd.DataFrame, bars: pd.DataFrame, initial_cash: float
) -> tuple[dict[str, float], pd.DataFrame]:
    benchmark = buy_and_hold_curve(bars, initial_cash)
    merged = strategy_curve[["timestamp", "equity"]].merge(
        benchmark, on="timestamp", how="inner", suffixes=("_strategy", "_benchmark")
    )
    strategy_metrics = _annualized_metrics(merged["equity_strategy"], merged["timestamp"])
    benchmark_metrics = _annualized_metrics(merged["equity_benchmark"], merged["timestamp"])
    sr = merged["equity_strategy"].pct_change().fillna(0.0)
    br = merged["equity_benchmark"].pct_change().fillna(0.0)
    variance = float(br.var(ddof=0))
    beta = 0.0 if variance == 0.0 else float(sr.cov(br, ddof=0) / variance)
    alpha = float(strategy_metrics["cagr"] - beta * benchmark_metrics["cagr"])
    exposure = 0.0
    if "target" in strategy_curve.columns:
        exposure = float((strategy_curve["target"].astype(float) > 0.0).mean())
    metrics: dict[str, float] = {}
    metrics.update({f"strategy_{key}": value for key, value in strategy_metrics.items()})
    metrics.update({f"benchmark_{key}": value for key, value in benchmark_metrics.items()})
    metrics.update(
        {
            "excess_total_return": strategy_metrics["total_return"]
            - benchmark_metrics["total_return"],
            "excess_cagr": strategy_metrics["cagr"] - benchmark_metrics["cagr"],
            "alpha": alpha,
            "beta": beta,
            "correlation": float(sr.corr(br)) if sr.std(ddof=0) and br.std(ddof=0) else 0.0,
            "market_exposure": exposure,
        }
    )
    return metrics, merged
