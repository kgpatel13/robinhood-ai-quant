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
    entries = int((trades["side"] == "BUY").sum()) if not trades.empty else 0
    exits = int((trades["side"] == "SELL").sum()) if not trades.empty else 0
    open_positions = max(entries - exits, 0)
    realized_pnl = float(completed["realized_pnl"].sum()) if not completed.empty else 0.0
    unrealized_pnl = (
        float(equity_curve["unrealized_pnl"].iloc[-1])
        if "unrealized_pnl" in equity_curve.columns
        else 0.0
    )
    total_costs = 0.0
    if not trades.empty:
        total_costs = float(trades["commission"].sum())
        if "fee" in trades.columns:
            total_costs += float(trades["fee"].sum())
    average_hold = (
        float(completed["holding_days"].mean())
        if not completed.empty and "holding_days" in completed.columns
        else 0.0
    )
    calmar = 0.0 if drawdown.min() == 0.0 else float(cagr / abs(drawdown.min()))
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
        "entries": entries,
        "exits": exits,
        "completed_trades": exits,
        "open_positions": open_positions,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_costs": total_costs,
        "average_holding_days": average_hold,
        "calmar_ratio": calmar,
        "win_rate": float(len(wins) / len(completed)) if len(completed) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else 0.0,
    }
