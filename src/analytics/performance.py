from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EquitySnapshot:
    timestamp: datetime
    equity: float
    cash: float
    market_value: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int


@dataclass(frozen=True)
class PerformanceSummary:
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    maximum_drawdown: float
    best_period_return: float
    worst_period_return: float
    observations: int


@dataclass(frozen=True)
class BenchmarkComparison:
    portfolio_return: float
    benchmark_return: float
    excess_return: float
    beta: float
    alpha_annualized: float
    correlation: float


class EquityJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, snapshot: EquitySnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(snapshot)
        payload["timestamp"] = snapshot.timestamp.astimezone(UTC).isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(
                columns=[
                    "equity",
                    "cash",
                    "market_value",
                    "realized_pnl",
                    "unrealized_pnl",
                    "open_positions",
                ]
            )
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp").sort_index()


def summarize_equity(equity: pd.Series, periods_per_year: float = 252.0) -> PerformanceSummary:
    clean = pd.to_numeric(equity, errors="coerce").dropna()
    if clean.empty:
        return PerformanceSummary(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    returns = clean.pct_change().dropna()
    total_return = float(clean.iloc[-1] / clean.iloc[0] - 1.0) if clean.iloc[0] else 0.0
    observations = len(clean)
    years = max((observations - 1) / periods_per_year, 1.0 / periods_per_year)
    annualized_return = float((1.0 + total_return) ** (1.0 / years) - 1.0)
    volatility = (
        float(returns.std(ddof=0) * np.sqrt(periods_per_year)) if not returns.empty else 0.0
    )
    sharpe = annualized_return / volatility if volatility > 0 else 0.0
    drawdown = clean / clean.cummax() - 1.0
    return PerformanceSummary(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=volatility,
        sharpe_ratio=sharpe,
        maximum_drawdown=float(drawdown.min()),
        best_period_return=float(returns.max()) if not returns.empty else 0.0,
        worst_period_return=float(returns.min()) if not returns.empty else 0.0,
        observations=observations,
    )


def rolling_metrics(equity: pd.Series, window: int = 20) -> pd.DataFrame:
    clean = pd.to_numeric(equity, errors="coerce").dropna()
    returns = clean.pct_change()
    result = pd.DataFrame(index=clean.index)
    result["rolling_return"] = clean.pct_change(window)
    result["rolling_volatility"] = returns.rolling(window).std(ddof=0) * np.sqrt(252.0)
    rolling_mean = returns.rolling(window).mean() * 252.0
    result["rolling_sharpe"] = rolling_mean / result["rolling_volatility"].replace(0.0, np.nan)
    result["drawdown"] = clean / clean.cummax() - 1.0
    return result


def compare_benchmark(
    portfolio_equity: pd.Series,
    benchmark_prices: pd.Series,
    periods_per_year: float = 252.0,
) -> BenchmarkComparison:
    joined = pd.concat(
        [portfolio_equity.rename("portfolio"), benchmark_prices.rename("benchmark")], axis=1
    ).dropna()
    if len(joined) < 2:
        return BenchmarkComparison(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    returns = joined.pct_change().dropna()
    portfolio_return = float(joined["portfolio"].iloc[-1] / joined["portfolio"].iloc[0] - 1.0)
    benchmark_return = float(joined["benchmark"].iloc[-1] / joined["benchmark"].iloc[0] - 1.0)
    benchmark_variance = float(returns["benchmark"].var(ddof=0))
    covariance_value = returns.cov(ddof=0).loc["portfolio", "benchmark"]
    covariance = float(np.asarray(covariance_value).item())
    beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0
    alpha = float(
        (returns["portfolio"].mean() - beta * returns["benchmark"].mean()) * periods_per_year
    )
    correlation = float(returns["portfolio"].corr(returns["benchmark"]))
    if np.isnan(correlation):
        correlation = 0.0
    return BenchmarkComparison(
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
        excess_return=portfolio_return - benchmark_return,
        beta=beta,
        alpha_annualized=alpha,
        correlation=correlation,
    )


def calculate_metrics(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, float | int]:
    """Calculate the legacy backtest metric dictionary.

    This compatibility API is retained for the original single-asset and
    portfolio backtest engines while the newer analytics dashboard uses
    :func:`summarize_equity`.
    """
    if equity_curve.empty or "equity" not in equity_curve.columns:
        raise ValueError("equity_curve must contain at least one equity observation")

    equity = pd.to_numeric(equity_curve["equity"], errors="coerce").dropna()
    if equity.empty:
        raise ValueError("equity_curve contains no valid equity observations")

    returns = equity.pct_change().fillna(0.0)
    elapsed_days = 0
    if "timestamp" in equity_curve.columns and len(equity_curve) > 1:
        start = pd.Timestamp(equity_curve["timestamp"].iloc[0])
        end = pd.Timestamp(equity_curve["timestamp"].iloc[-1])
        elapsed_days = max((end - start).days, 0)
    years = max(elapsed_days / 365.25, 1.0 / 365.25)

    initial_equity = float(equity.iloc[0])
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / initial_equity - 1.0 if initial_equity else 0.0
    cagr = (final_equity / initial_equity) ** (1.0 / years) - 1.0 if initial_equity else 0.0
    return_deviation = float(returns.std(ddof=0))
    volatility = return_deviation * math.sqrt(252.0)
    sharpe = (
        0.0
        if return_deviation == 0.0
        else float(returns.mean()) / return_deviation * math.sqrt(252.0)
    )
    downside = returns.where(returns < 0.0, 0.0)
    downside_deviation = float(downside.std(ddof=0))
    sortino = (
        0.0
        if downside_deviation == 0.0
        else float(returns.mean()) / downside_deviation * math.sqrt(252.0)
    )
    drawdown = equity / equity.cummax() - 1.0

    completed = trades[trades["side"] == "SELL"] if not trades.empty else trades
    wins = completed[completed["realized_pnl"] > 0] if not completed.empty else completed
    losses = completed[completed["realized_pnl"] < 0] if not completed.empty else completed
    gross_profit = float(wins["realized_pnl"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["realized_pnl"].sum())) if not losses.empty else 0.0
    entries = int((trades["side"] == "BUY").sum()) if not trades.empty else 0
    exits = int((trades["side"] == "SELL").sum()) if not trades.empty else 0
    realized_pnl = float(completed["realized_pnl"].sum()) if not completed.empty else 0.0
    unrealized_pnl = (
        float(equity_curve["unrealized_pnl"].iloc[-1])
        if "unrealized_pnl" in equity_curve.columns
        else 0.0
    )

    total_costs = 0.0
    if not trades.empty:
        if "commission" in trades.columns:
            total_costs += float(trades["commission"].sum())
        if "fee" in trades.columns:
            total_costs += float(trades["fee"].sum())
        if "slippage_cost" in trades.columns:
            total_costs += float(trades["slippage_cost"].sum())

    average_hold = (
        float(completed["holding_days"].mean())
        if not completed.empty and "holding_days" in completed.columns
        else 0.0
    )
    max_drawdown = float(drawdown.min())
    calmar = 0.0 if max_drawdown == 0.0 else float(cagr / abs(max_drawdown))

    return {
        "initial_equity": initial_equity,
        "final_equity": final_equity,
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annualized_volatility": float(volatility),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown": max_drawdown,
        "trade_count": int(len(completed)),
        "entries": entries,
        "exits": exits,
        "completed_trades": exits,
        "open_positions": max(entries - exits, 0),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_costs": total_costs,
        "average_holding_days": average_hold,
        "average_exposure": (
            float(equity_curve["exposure_ratio"].mean())
            if "exposure_ratio" in equity_curve.columns
            else 0.0
        ),
        "peak_exposure": (
            float(equity_curve["exposure_ratio"].max())
            if "exposure_ratio" in equity_curve.columns
            else 0.0
        ),
        "calmar_ratio": calmar,
        "win_rate": float(len(wins) / len(completed)) if len(completed) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else 0.0,
    }
