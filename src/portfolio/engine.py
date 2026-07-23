from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.analytics.performance import calculate_metrics
from src.portfolio.allocation import equal_weights, fixed_weights, inverse_volatility_weights
from src.portfolio.models import PortfolioBacktestConfig, PortfolioBacktestResult
from src.strategies.base import Strategy

_REQUIRED_COLUMNS = {"timestamp", "open", "close"}


class PortfolioBacktestEngine:
    def run(
        self,
        datasets: Mapping[str, pd.DataFrame],
        strategy: Strategy,
        config: PortfolioBacktestConfig,
    ) -> PortfolioBacktestResult:
        if len(datasets) < 2:
            raise ValueError("Portfolio backtesting requires at least two assets")
        symbols = sorted(datasets)
        prepared = {
            symbol: self._prepare(symbol, frame, strategy) for symbol, frame in datasets.items()
        }
        common_dates = self._common_dates(prepared)
        if len(common_dates) < strategy.metadata.required_history + 2:
            raise ValueError("Insufficient overlapping history across portfolio assets")

        opens = pd.DataFrame(
            {symbol: frame.set_index("timestamp")["open"] for symbol, frame in prepared.items()}
        ).loc[common_dates]
        closes = pd.DataFrame(
            {symbol: frame.set_index("timestamp")["close"] for symbol, frame in prepared.items()}
        ).loc[common_dates]
        signals = pd.DataFrame(
            {
                symbol: strategy.generate_signals(frame).set_axis(frame["timestamp"]).clip(0.0, 1.0)
                for symbol, frame in prepared.items()
            }
        ).loc[common_dates]
        executable_signals = signals.shift(1).fillna(0.0)
        returns = closes.pct_change()

        cash = config.initial_cash
        quantities = {symbol: 0.0 for symbol in symbols}
        average_cost = {symbol: 0.0 for symbol in symbols}
        previous_targets = {symbol: 0.0 for symbol in symbols}
        trades: list[dict[str, Any]] = []
        equity_rows: list[dict[str, Any]] = []
        holdings_rows: list[dict[str, Any]] = []
        weight_rows: list[dict[str, Any]] = []
        slippage = config.slippage_bps / 10_000.0

        for position, timestamp in enumerate(common_dates):
            open_prices = {symbol: self._scalar(opens, timestamp, symbol) for symbol in symbols}
            close_prices = {symbol: self._scalar(closes, timestamp, symbol) for symbol in symbols}
            open_market_value = 0.0
            for symbol in symbols:
                open_market_value += quantities[symbol] * open_prices[symbol]
            open_equity = cash + open_market_value
            target_weights = previous_targets
            if self._is_rebalance_date(common_dates, position, config.rebalance_frequency):
                active = [
                    symbol
                    for symbol in symbols
                    if self._scalar(executable_signals, timestamp, symbol) > 0.0
                ]
                target_weights = self._allocate(active, symbols, returns.iloc[:position], config)
                investable = 1.0 - config.cash_buffer_pct
                target_weights = {
                    symbol: target_weights.get(symbol, 0.0) * investable for symbol in symbols
                }

            desired_values = {
                symbol: open_equity * target_weights.get(symbol, 0.0) for symbol in symbols
            }
            deltas = {
                symbol: desired_values[symbol] - quantities[symbol] * open_prices[symbol]
                for symbol in symbols
            }

            for symbol in symbols:
                if deltas[symbol] < -1e-9:
                    cash = self._execute_sell(
                        timestamp,
                        symbol,
                        -deltas[symbol],
                        open_prices[symbol],
                        slippage,
                        config,
                        cash,
                        quantities,
                        average_cost,
                        trades,
                    )
            buy_requirements = {symbol: value for symbol, value in deltas.items() if value > 1e-9}
            total_required = (
                sum(buy_requirements.values()) + len(buy_requirements) * config.commission_per_order
            )
            scale = (
                1.0
                if total_required <= cash or total_required <= 0
                else max(cash, 0.0) / total_required
            )
            for symbol, value in buy_requirements.items():
                cash = self._execute_buy(
                    timestamp,
                    symbol,
                    value * scale,
                    open_prices[symbol],
                    slippage,
                    config,
                    cash,
                    quantities,
                    average_cost,
                    trades,
                )

            close_market_value = 0.0
            for symbol in symbols:
                close_market_value += quantities[symbol] * close_prices[symbol]
            close_equity = cash + close_market_value
            equity_rows.append({"timestamp": timestamp, "cash": cash, "equity": close_equity})
            weight_row: dict[str, Any] = {"timestamp": timestamp}
            for symbol in symbols:
                market_value = quantities[symbol] * close_prices[symbol]
                holdings_rows.append(
                    {
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "quantity": quantities[symbol],
                        "close": close_prices[symbol],
                        "market_value": market_value,
                        "weight": market_value / close_equity if close_equity else 0.0,
                    }
                )
                weight_row[symbol] = target_weights.get(symbol, 0.0)
            weight_rows.append(weight_row)
            previous_targets = target_weights

        equity_curve = pd.DataFrame(equity_rows)
        trade_frame = pd.DataFrame(
            trades,
            columns=[
                "timestamp",
                "symbol",
                "side",
                "price",
                "quantity",
                "commission",
                "realized_pnl",
            ],
        )
        holdings = pd.DataFrame(holdings_rows)
        target_frame = pd.DataFrame(weight_rows)
        metrics = calculate_metrics(equity_curve, trade_frame)
        metrics["asset_count"] = len(symbols)
        metrics["order_count"] = len(trade_frame)
        return PortfolioBacktestResult(
            equity_curve=equity_curve,
            trades=trade_frame,
            holdings=holdings,
            target_weights=target_frame,
            metrics=metrics,
        )

    @staticmethod
    def _scalar(frame: pd.DataFrame, timestamp: pd.Timestamp, symbol: str) -> float:
        value: Any = frame.at[timestamp, symbol]
        return float(value)

    @staticmethod
    def _prepare(symbol: str, frame: pd.DataFrame, strategy: Strategy) -> pd.DataFrame:
        missing = _REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(f"{symbol} is missing required columns: {sorted(missing)}")
        ordered = frame.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        if len(ordered) < strategy.metadata.required_history + 2:
            raise ValueError(f"{symbol} has insufficient history")
        return ordered

    @staticmethod
    def _common_dates(prepared: Mapping[str, pd.DataFrame]) -> pd.DatetimeIndex:
        common: pd.DatetimeIndex | None = None
        for frame in prepared.values():
            dates = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"]))
            common = dates if common is None else common.intersection(dates)
        if common is None:
            return pd.DatetimeIndex([])
        return common.sort_values()

    @staticmethod
    def _is_rebalance_date(dates: pd.DatetimeIndex, position: int, frequency: str) -> bool:
        if position == 0 or frequency == "daily":
            return True
        current = dates[position]
        previous = dates[position - 1]
        if frequency == "weekly":
            return current.isocalendar().week != previous.isocalendar().week
        if frequency == "monthly":
            return current.month != previous.month or current.year != previous.year
        raise ValueError(f"Unsupported rebalance frequency: {frequency}")

    @staticmethod
    def _allocate(
        active: list[str],
        symbols: list[str],
        returns: pd.DataFrame,
        config: PortfolioBacktestConfig,
    ) -> dict[str, float]:
        if not active:
            return {symbol: 0.0 for symbol in symbols}
        if config.allocation_method == "equal":
            active_weights = equal_weights(active, config.max_asset_weight)
        elif config.allocation_method == "fixed":
            base = fixed_weights(symbols, config.fixed_weights, config.max_asset_weight)
            active_weights = {symbol: base[symbol] for symbol in active}
            total = sum(active_weights.values())
            if total <= 0:
                return {symbol: 0.0 for symbol in symbols}
            active_weights = {symbol: value / total for symbol, value in active_weights.items()}
        elif config.allocation_method == "inverse_volatility":
            window = returns.tail(config.volatility_lookback)
            active_weights = inverse_volatility_weights(window, active, config.max_asset_weight)
        else:
            raise ValueError(f"Unsupported allocation method: {config.allocation_method}")
        return {symbol: active_weights.get(symbol, 0.0) for symbol in symbols}

    @staticmethod
    def _execute_sell(
        timestamp: pd.Timestamp,
        symbol: str,
        dollar_value: float,
        open_price: float,
        slippage: float,
        config: PortfolioBacktestConfig,
        cash: float,
        quantities: dict[str, float],
        average_cost: dict[str, float],
        trades: list[dict[str, Any]],
    ) -> float:
        fill = open_price * (1.0 - slippage)
        quantity = min(dollar_value / open_price, quantities[symbol])
        if quantity <= 1e-12:
            return cash
        proceeds = quantity * fill - config.commission_per_order
        realized = quantity * (fill - average_cost[symbol]) - config.commission_per_order
        quantities[symbol] -= quantity
        if quantities[symbol] <= 1e-12:
            quantities[symbol] = 0.0
            average_cost[symbol] = 0.0
        trades.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "side": "SELL",
                "price": fill,
                "quantity": quantity,
                "commission": config.commission_per_order,
                "realized_pnl": realized,
            }
        )
        return cash + proceeds

    @staticmethod
    def _execute_buy(
        timestamp: pd.Timestamp,
        symbol: str,
        dollar_value: float,
        open_price: float,
        slippage: float,
        config: PortfolioBacktestConfig,
        cash: float,
        quantities: dict[str, float],
        average_cost: dict[str, float],
        trades: list[dict[str, Any]],
    ) -> float:
        fill = open_price * (1.0 + slippage)
        available = max(cash - config.commission_per_order, 0.0)
        quantity = min(dollar_value / open_price, available / fill)
        if quantity <= 1e-12:
            return cash
        cost = quantity * fill + config.commission_per_order
        old_quantity = quantities[symbol]
        new_quantity = old_quantity + quantity
        average_cost[symbol] = (
            old_quantity * average_cost[symbol] + quantity * fill + config.commission_per_order
        ) / new_quantity
        quantities[symbol] = new_quantity
        trades.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "side": "BUY",
                "price": fill,
                "quantity": quantity,
                "commission": config.commission_per_order,
                "realized_pnl": 0.0,
            }
        )
        return cash - cost
