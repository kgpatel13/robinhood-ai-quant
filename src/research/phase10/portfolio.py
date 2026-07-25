from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import pandas as pd


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01
    maximum_position_percent: float = 0.10
    maximum_concurrent_positions: int = 10
    one_position_per_symbol: bool = True
    cooldown_bars_after_exit: int = 1

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.risk_per_trade <= 1:
            raise ValueError("risk_per_trade must be in (0, 1]")
        if not 0 < self.maximum_position_percent <= 1:
            raise ValueError("maximum_position_percent must be in (0, 1]")
        if self.maximum_concurrent_positions < 1:
            raise ValueError("maximum_concurrent_positions must be positive")
        if self.cooldown_bars_after_exit < 0:
            raise ValueError("cooldown_bars_after_exit cannot be negative")


@dataclass
class _Position:
    symbol: str
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: float
    position_value: float
    row: dict[str, object]


def _safe_price(
    prices: pd.DataFrame, symbol: str, timestamp: pd.Timestamp, fallback: float
) -> float:
    if symbol not in prices.columns:
        return fallback
    series = prices[symbol].loc[:timestamp].dropna()
    return float(series.iloc[-1]) if not series.empty else fallback


def _annualized_metrics(equity: pd.DataFrame) -> tuple[float, float, float, float, float]:
    if equity.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    values = equity["equity"].astype(float)
    returns = values.pct_change().fillna(0.0)
    drawdown = values / values.cummax() - 1.0
    maximum_drawdown = float(drawdown.min())
    ending_timestamp = pd.Timestamp(equity["timestamp"].iloc[-1])
    starting_timestamp = pd.Timestamp(equity["timestamp"].iloc[0])
    elapsed_days = max((ending_timestamp - starting_timestamp).days, 1)
    years = elapsed_days / 365.25
    total_return = float(values.iloc[-1] / values.iloc[0] - 1.0)
    cagr = float((values.iloc[-1] / values.iloc[0]) ** (1.0 / years) - 1.0) if years > 0 else 0.0
    deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / deviation * math.sqrt(365.0)) if deviation > 0 else 0.0
    downside = returns[returns < 0]
    downside_deviation = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = (
        float(returns.mean() / downside_deviation * math.sqrt(365.0))
        if downside_deviation > 0
        else 0.0
    )
    return total_return, cagr, maximum_drawdown, sharpe, sortino if math.isfinite(sortino) else 0.0


def simulate_portfolio(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    config: PortfolioConfig,
    scenario: Mapping[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], pd.DataFrame]:
    if signals.empty:
        return pd.DataFrame(), pd.DataFrame(), {**scenario, "trades": 0}, pd.DataFrame()

    working = signals.copy()
    for column in ("entry_timestamp", "exit_timestamp"):
        working[column] = pd.to_datetime(working[column], utc=True)
    working = working.sort_values(["entry_timestamp", "opportunity_score"], ascending=[True, False])

    cash = config.initial_capital
    open_positions: list[_Position] = []
    completed: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    cooldown_until: dict[str, pd.Timestamp] = {}
    equity_rows: list[dict[str, object]] = []

    start = cast(pd.Timestamp, working["entry_timestamp"].min()).normalize()
    end = cast(pd.Timestamp, working["exit_timestamp"].max()).normalize()
    entries_by_day = {
        cast(pd.Timestamp, day).normalize(): group
        for day, group in working.groupby(working["entry_timestamp"].dt.normalize())
    }

    for day in pd.date_range(start, end, freq="D", tz="UTC"):
        exiting = [
            position for position in open_positions if position.exit_timestamp.normalize() <= day
        ]
        for position in exiting:
            proceeds = position.shares * position.exit_price
            cash += proceeds
            pnl = proceeds - position.position_value
            completed.append(
                {
                    **position.row,
                    **scenario,
                    "position_value": position.position_value,
                    "shares": position.shares,
                    "realized_pnl": pnl,
                    "portfolio_return_on_capital": pnl / config.initial_capital,
                }
            )
            cooldown_until[position.symbol] = day + pd.Timedelta(
                days=config.cooldown_bars_after_exit
            )
            open_positions.remove(position)

        day_entries = entries_by_day.get(day)
        if day_entries is not None:
            for _, signal in day_entries.iterrows():
                symbol = str(signal["symbol"])
                reason = ""
                if config.one_position_per_symbol and any(
                    position.symbol == symbol for position in open_positions
                ):
                    reason = "position_already_open"
                elif symbol in cooldown_until and day <= cooldown_until[symbol]:
                    reason = "cooldown_active"
                elif len(open_positions) >= config.maximum_concurrent_positions:
                    reason = "portfolio_capacity_reached"

                equity_before = cash + sum(
                    position.shares
                    * _safe_price(prices, position.symbol, day, position.entry_price)
                    for position in open_positions
                )
                entry_price = float(signal["entry_price"])
                stop_price = float(signal["stop_price"])
                stop_fraction = max((entry_price - stop_price) / entry_price, 0.0)
                if not reason and stop_fraction <= 0:
                    reason = "invalid_position_size"
                risk_budget = equity_before * config.risk_per_trade
                risk_position_value = risk_budget / stop_fraction if stop_fraction > 0 else 0.0
                position_value = min(
                    risk_position_value,
                    equity_before * config.maximum_position_percent,
                    cash,
                )
                if not reason and position_value <= 0:
                    reason = "insufficient_cash"
                if reason:
                    skipped.append(
                        {
                            **scenario,
                            "symbol": symbol,
                            "entry_timestamp": signal["entry_timestamp"],
                            "opportunity_score": float(signal["opportunity_score"]),
                            "skip_reason": reason,
                        }
                    )
                    continue

                shares = position_value / entry_price
                cash -= position_value
                open_positions.append(
                    _Position(
                        symbol=symbol,
                        entry_timestamp=cast(pd.Timestamp, signal["entry_timestamp"]),
                        exit_timestamp=cast(pd.Timestamp, signal["exit_timestamp"]),
                        entry_price=entry_price,
                        exit_price=float(signal["exit_price"]),
                        shares=shares,
                        position_value=position_value,
                        row=cast(dict[str, object], signal.to_dict()),
                    )
                )

        market_value = sum(
            position.shares * _safe_price(prices, position.symbol, day, position.entry_price)
            for position in open_positions
        )
        equity_value = cash + market_value
        equity_rows.append(
            {
                **scenario,
                "timestamp": day,
                "cash": cash,
                "market_value": market_value,
                "equity": equity_value,
                "open_positions": len(open_positions),
                "exposure": market_value / equity_value if equity_value > 0 else 0.0,
            }
        )

    trades = pd.DataFrame(completed)
    equity = pd.DataFrame(equity_rows)
    skipped_frame = pd.DataFrame(skipped)
    total_return, cagr, maximum_drawdown, sharpe, sortino = _annualized_metrics(equity)
    trade_returns = (
        trades["realized_pnl"].astype(float) if not trades.empty else pd.Series(dtype=float)
    )
    gains = float(trade_returns[trade_returns > 0].sum())
    losses = abs(float(trade_returns[trade_returns < 0].sum()))
    summary: dict[str, object] = {
        **scenario,
        "initial_capital": config.initial_capital,
        "ending_equity": (
            float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_capital
        ),
        "total_return": total_return,
        "cagr": cagr,
        "maximum_drawdown": maximum_drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": cagr / abs(maximum_drawdown) if maximum_drawdown < 0 else 0.0,
        "trades": len(trades),
        "win_rate": float((trade_returns > 0).mean()) if not trades.empty else 0.0,
        "profit_factor": gains / losses if losses > 0 else (math.inf if gains > 0 else 0.0),
        "average_trade_pnl": float(trade_returns.mean()) if not trades.empty else 0.0,
        "average_exposure": float(equity["exposure"].mean()) if not equity.empty else 0.0,
        "maximum_concurrent_positions": (
            int(equity["open_positions"].max()) if not equity.empty else 0
        ),
        "skipped_signals": len(skipped_frame),
    }
    return trades, equity, summary, skipped_frame


def period_performance(equity: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    frame = equity.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if frequency == "year":
        frame["period"] = frame["timestamp"].dt.year.astype(str)
    elif frequency == "month":
        frame["period"] = frame["timestamp"].dt.strftime("%Y-%m")
    else:
        raise ValueError("frequency must be 'year' or 'month'")
    rows: list[dict[str, object]] = []
    scenario_columns = ["asset_class", "holding_period", "threshold"]
    for raw_key, group in frame.groupby([*scenario_columns, "period"], observed=True):
        if not isinstance(raw_key, tuple) or len(raw_key) != 4:
            raise ValueError(f"Unexpected period grouping key: {raw_key!r}")
        asset_class, holding_period, threshold, period = raw_key
        values = group.sort_values("timestamp")["equity"].astype(float)
        drawdown = values / values.cummax() - 1.0
        rows.append(
            {
                "asset_class": str(asset_class),
                "holding_period": int(str(holding_period)),
                "threshold": float(str(threshold)),
                "period": str(period),
                "return": float(values.iloc[-1] / values.iloc[0] - 1.0),
                "maximum_drawdown": float(drawdown.min()),
                "average_exposure": float(group["exposure"].mean()),
            }
        )
    return pd.DataFrame(rows)
