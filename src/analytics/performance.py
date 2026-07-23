from __future__ import annotations

import math

import pandas as pd


def calculate_metrics(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float | int]:
    equity = equity_curve["equity"].astype(float)
    returns = equity.pct_change().fillna(0.0)
    elapsed_days = (equity_curve["timestamp"].iloc[-1] - equity_curve["timestamp"].iloc[0]).days
    years = max(elapsed_days / 365.25, 1 / 365.25)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0
    volatility = returns.std(ddof=0) * math.sqrt(252.0)
    return_deviation = returns.std(ddof=0)
    sharpe = 0.0 if return_deviation == 0 else returns.mean() / return_deviation * math.sqrt(252.0)
    downside = returns.where(returns < 0.0, 0.0)
    downside_deviation = downside.std(ddof=0)
    sortino = (
        0.0 if downside_deviation == 0 else returns.mean() / downside_deviation * math.sqrt(252.0)
    )
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    completed = trades[trades["side"] == "SELL"] if not trades.empty else trades
    wins = completed[completed["realized_pnl"] > 0] if not completed.empty else completed
    losses = completed[completed["realized_pnl"] < 0] if not completed.empty else completed
    gross_profit = float(wins["realized_pnl"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["realized_pnl"].sum())) if not losses.empty else 0.0
    return {
        "initial_equity": float(equity.iloc[0]),
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annualized_volatility": float(volatility),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown": float(drawdown.min()),
        "trade_count": int(len(completed)),
        "win_rate": float(len(wins) / len(completed)) if len(completed) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else 0.0,
    }
