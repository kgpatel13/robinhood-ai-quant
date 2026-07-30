from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import numpy as np
import pandas as pd

from src.rotation_engine.models import (
    AssetClass,
    ExitReason,
    Opportunity,
    Position,
    RotationBacktestResult,
    RotationConfig,
    RotationTrade,
)
from src.rotation_engine.strategies import RotationStrategyLibrary


class RotationBacktestEngine:
    """Shared-capital, point-in-time portfolio rotation simulator."""

    def __init__(self, strategy_library: RotationStrategyLibrary | None = None) -> None:
        self.library = strategy_library or RotationStrategyLibrary()

    def run(
        self,
        datasets: Mapping[str, pd.DataFrame],
        asset_classes: Mapping[str, AssetClass],
        config: RotationConfig | None = None,
        *,
        test_start: str | datetime | pd.Timestamp | None = None,
        test_end: str | datetime | pd.Timestamp | None = None,
    ) -> RotationBacktestResult:
        settings = config or RotationConfig()
        prepared = {symbol.upper(): self._prepare(frame) for symbol, frame in datasets.items()}
        if not prepared:
            raise ValueError("at least one dataset is required")

        required_history = max(int(getattr(self.library, "required_history", 65)), 2)
        start_timestamp = self._normalize_boundary(test_start)
        end_timestamp = self._normalize_boundary(test_end)

        if start_timestamp is None:
            start_timestamp = self._common_start_timestamp(prepared)
            alignment = "latest_required_history_start"
        else:
            alignment = "explicit_test_window_dynamic_eligibility"

        if end_timestamp is not None and end_timestamp < start_timestamp:
            raise ValueError("test_end must be on or after test_start")

        eligible_assets = {
            symbol: bars
            for symbol, bars in prepared.items()
            if len(bars[bars.index < start_timestamp]) >= required_history
            or len(bars[bars.index <= start_timestamp]) >= required_history
            or bars.index.max() >= start_timestamp
        }
        if not eligible_assets:
            raise ValueError("no datasets overlap the requested test window")

        timestamp_sets: list[set[pd.Timestamp]] = []
        for bars in eligible_assets.values():
            mask = bars.index >= start_timestamp
            if end_timestamp is not None:
                mask &= bars.index <= end_timestamp
            timestamp_sets.append(set(pd.DatetimeIndex(bars.index[mask])))

        common_timestamps = sorted(set().union(*timestamp_sets)) if timestamp_sets else []
        if not common_timestamps:
            raise ValueError("no timestamps found inside the requested test window")

        cash = settings.initial_cash
        positions: dict[str, Position] = {}
        trades: list[RotationTrade] = []
        equity_curve: list[tuple[datetime, float]] = []
        decisions: list[Mapping[str, object]] = [
            {
                "action": "backtest_start",
                "timestamp": str(common_timestamps[0]),
                "requested_start": str(start_timestamp),
                "requested_end": str(end_timestamp) if end_timestamp is not None else None,
                "alignment": alignment,
                "assets": sorted(eligible_assets),
                "required_history": required_history,
            }
        ]

        for raw_timestamp in common_timestamps:
            timestamp = pd.Timestamp(raw_timestamp).to_pydatetime()
            prices = self._prices(eligible_assets, raw_timestamp)
            if not prices:
                continue

            cash = self._manage_positions(
                raw_timestamp,
                prices,
                eligible_assets,
                positions,
                trades,
                decisions,
                cash,
                settings,
            )
            opportunities = self._opportunities(
                raw_timestamp,
                eligible_assets,
                asset_classes,
                positions,
            )
            cash = self._rotate_and_enter(
                raw_timestamp,
                opportunities,
                prices,
                positions,
                trades,
                decisions,
                cash,
                settings,
            )
            equity = cash + sum(
                position.market_value(prices.get(symbol, position.entry_price))
                for symbol, position in positions.items()
            )
            equity_curve.append((timestamp, equity))

        final_timestamp = pd.Timestamp(common_timestamps[-1])
        prices = self._prices(eligible_assets, final_timestamp)
        for symbol in list(positions):
            cash = self._close_position(
                symbol,
                final_timestamp,
                prices.get(symbol, positions[symbol].entry_price),
                ExitReason.END_OF_TEST,
                positions,
                trades,
                cash,
                settings,
            )

        metrics = self._metrics(settings.initial_cash, cash, trades, equity_curve)
        metrics["asset_count"] = len(eligible_assets)
        return RotationBacktestResult(
            metrics,
            tuple(trades),
            tuple(equity_curve),
            tuple(decisions),
        )

    @staticmethod
    def _normalize_boundary(
        value: str | datetime | pd.Timestamp | None,
    ) -> pd.Timestamp | None:
        if value is None:
            return None
        boundary = pd.Timestamp(value)
        if boundary.tzinfo is None:
            return boundary.tz_localize("UTC")
        return boundary.tz_convert("UTC")

    def _common_start_timestamp(
        self,
        prepared: Mapping[str, pd.DataFrame],
    ) -> pd.Timestamp:
        required_history = max(int(getattr(self.library, "required_history", 65)), 2)
        usable_starts: list[pd.Timestamp] = []

        for symbol, bars in prepared.items():
            if len(bars) < required_history:
                raise ValueError(
                    f"{symbol} has {len(bars)} rows; at least {required_history} are required"
                )
            usable_starts.append(pd.Timestamp(bars.index[required_history - 1]))

        return max(usable_starts)

    def _opportunities(
        self,
        timestamp: pd.Timestamp,
        prepared: Mapping[str, pd.DataFrame],
        asset_classes: Mapping[str, AssetClass],
        positions: Mapping[str, Position],
    ) -> list[Opportunity]:
        required_history = max(int(getattr(self.library, "required_history", 65)), 2)
        returns_20: dict[str, float] = {}

        for symbol, bars in prepared.items():
            history = bars[bars.index <= timestamp]
            if len(history) >= required_history:
                returns_20[symbol] = float(
                    history["close"].iloc[-1] / history["close"].iloc[-21] - 1.0
                )

        ordered = sorted(returns_20, key=returns_20.get)  # type: ignore[arg-type]
        percentiles = {
            symbol: (index + 1) / max(len(ordered), 1) for index, symbol in enumerate(ordered)
        }

        opportunities: list[Opportunity] = []
        for symbol, bars in prepared.items():
            if symbol in positions or timestamp not in bars.index:
                continue
            history = bars[bars.index <= timestamp]
            if len(history) < required_history:
                continue
            opportunity = self.library.assess(
                bars,
                timestamp=timestamp.to_pydatetime(),
                symbol=symbol,
                asset_class=asset_classes.get(symbol, AssetClass.STOCK),
                relative_strength=percentiles.get(symbol, 0.5),
            )
            if opportunity is not None:
                opportunities.append(opportunity)

        return sorted(
            opportunities,
            key=lambda item: (item.score, item.capital_efficiency),
            reverse=True,
        )

    def _manage_positions(
        self,
        timestamp: pd.Timestamp,
        prices: Mapping[str, float],
        prepared: Mapping[str, pd.DataFrame],
        positions: dict[str, Position],
        trades: list[RotationTrade],
        decisions: list[Mapping[str, object]],
        cash: float,
        config: RotationConfig,
    ) -> float:
        for symbol in list(positions):
            position = positions[symbol]
            if symbol not in prices:
                continue
            price = prices[symbol]
            position.days_held = max(
                0,
                (timestamp.to_pydatetime().date() - position.entry_time.date()).days,
            )
            position.highest_price = max(position.highest_price, price)
            bars = prepared[symbol][prepared[symbol].index <= timestamp]
            atr = self._atr(bars)
            position.trailing_stop = max(
                position.trailing_stop,
                position.highest_price - atr * config.trailing_atr_multiple,
            )
            opportunity = self.library.assess(
                prepared[symbol],
                timestamp=timestamp.to_pydatetime(),
                symbol=symbol,
                asset_class=position.asset_class,
            )
            position.last_score = opportunity.score if opportunity is not None else 0.0

            reason: ExitReason | None = None
            if price <= position.stop_price:
                reason = ExitReason.STOP_LOSS
            elif position.days_held >= config.min_hold_days and price <= position.trailing_stop:
                reason = ExitReason.TRAILING_STOP
            elif (
                position.days_held >= config.min_hold_days
                and position.last_score < config.min_entry_score * 0.75
            ):
                reason = ExitReason.SIGNAL_INVALIDATION
            elif (
                position.days_held >= config.no_progress_days
                and position.unrealized_return(price) < config.no_progress_return
            ):
                reason = ExitReason.NO_PROGRESS
            elif position.days_held >= config.max_hold_days:
                reason = ExitReason.MAX_HOLD

            if reason is not None:
                decisions.append(
                    {
                        "timestamp": str(timestamp),
                        "symbol": symbol,
                        "action": "exit",
                        "reason": reason.value,
                    }
                )
                cash = self._close_position(
                    symbol,
                    timestamp,
                    price,
                    reason,
                    positions,
                    trades,
                    cash,
                    config,
                )
        return cash

    def _rotate_and_enter(
        self,
        timestamp: pd.Timestamp,
        opportunities: list[Opportunity],
        prices: Mapping[str, float],
        positions: dict[str, Position],
        trades: list[RotationTrade],
        decisions: list[Mapping[str, object]],
        cash: float,
        config: RotationConfig,
    ) -> float:
        qualified = [item for item in opportunities if item.score >= config.min_entry_score]

        if qualified and len(positions) >= config.max_positions:
            weakest_symbol, weakest = min(
                positions.items(),
                key=lambda item: item[1].last_score,
            )
            best = qualified[0]
            current_price = prices.get(weakest_symbol, weakest.entry_price)
            if (
                weakest.days_held >= config.min_hold_days
                and best.score >= weakest.last_score + config.rotation_score_improvement
                and weakest.unrealized_return(current_price) >= -0.01
            ):
                decisions.append(
                    {
                        "timestamp": str(timestamp),
                        "symbol": weakest_symbol,
                        "action": "rotate",
                        "replacement": best.symbol,
                    }
                )
                cash = self._close_position(
                    weakest_symbol,
                    timestamp,
                    current_price,
                    ExitReason.ROTATION,
                    positions,
                    trades,
                    cash,
                    config,
                )

        for opportunity in qualified:
            if len(positions) >= config.max_positions:
                break
            if opportunity.symbol in positions:
                continue

            portfolio_value = cash + sum(
                position.market_value(prices.get(symbol, position.entry_price))
                for symbol, position in positions.items()
            )
            reserve = portfolio_value * config.cash_reserve_pct
            available = max(0.0, cash - reserve)
            if available <= 1.0:
                break

            max_pct = (
                config.max_crypto_position_pct
                if opportunity.asset_class == AssetClass.CRYPTO
                else config.max_position_pct
            )
            if opportunity.asset_class == AssetClass.CRYPTO:
                crypto_value = sum(
                    position.market_value(prices.get(symbol, position.entry_price))
                    for symbol, position in positions.items()
                    if position.asset_class == AssetClass.CRYPTO
                )
                available = min(
                    available,
                    max(
                        0.0,
                        portfolio_value * config.total_crypto_pct - crypto_value,
                    ),
                )

            stop_distance = max(
                opportunity.atr * config.stop_atr_multiple,
                opportunity.price * 0.01,
            )
            risk_budget = portfolio_value * config.risk_per_trade_pct
            risk_sized_value = risk_budget / (stop_distance / opportunity.price)
            allocation = min(
                available,
                portfolio_value * max_pct,
                risk_sized_value,
            )
            if allocation < 25.0:
                continue

            slippage = self._slippage(opportunity.asset_class, config)
            entry_price = opportunity.price * (1.0 + slippage)
            quantity = max(
                0.0,
                (allocation - config.commission_per_order) / entry_price,
            )
            if quantity <= 0:
                continue

            cost = quantity * entry_price + config.commission_per_order
            cash -= cost
            positions[opportunity.symbol] = Position(
                symbol=opportunity.symbol,
                asset_class=opportunity.asset_class,
                strategy=opportunity.strategy,
                entry_time=timestamp.to_pydatetime(),
                entry_price=entry_price,
                quantity=quantity,
                entry_score=opportunity.score,
                expected_holding_days=opportunity.expected_holding_days,
                stop_price=entry_price - stop_distance,
                trailing_stop=(entry_price - opportunity.atr * config.trailing_atr_multiple),
                highest_price=entry_price,
                last_score=opportunity.score,
            )
            decisions.append(
                {
                    "timestamp": str(timestamp),
                    "symbol": opportunity.symbol,
                    "action": "enter",
                    "strategy": opportunity.strategy,
                    "score": opportunity.score,
                    "allocation": allocation,
                }
            )
        return cash

    def _close_position(
        self,
        symbol: str,
        timestamp: pd.Timestamp,
        raw_price: float,
        reason: ExitReason,
        positions: dict[str, Position],
        trades: list[RotationTrade],
        cash: float,
        config: RotationConfig,
    ) -> float:
        position = positions.pop(symbol)
        slippage = self._slippage(position.asset_class, config)
        exit_price = raw_price * (1.0 - slippage)
        proceeds = position.quantity * exit_price - config.commission_per_order
        entry_value = position.quantity * position.entry_price
        gross_pnl = position.quantity * (exit_price - position.entry_price)
        costs = (
            entry_value * slippage
            + position.quantity * raw_price * slippage
            + 2 * config.commission_per_order
        )
        trades.append(
            RotationTrade(
                symbol=symbol,
                asset_class=position.asset_class,
                strategy=position.strategy,
                entry_time=position.entry_time,
                exit_time=timestamp.to_pydatetime(),
                entry_price=position.entry_price,
                exit_price=exit_price,
                quantity=position.quantity,
                gross_pnl=gross_pnl,
                costs=costs,
                net_pnl=proceeds - entry_value,
                holding_days=max(
                    0,
                    (timestamp.to_pydatetime().date() - position.entry_time.date()).days,
                ),
                exit_reason=reason,
            )
        )
        return cash + proceeds

    @staticmethod
    def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
        bars = frame.copy()
        if "timestamp" in bars.columns:
            bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)
            bars = bars.set_index("timestamp")
        else:
            bars.index = pd.to_datetime(bars.index, utc=True)

        required = {"open", "high", "low", "close", "volume"}
        missing = required.difference(bars.columns)
        if missing:
            raise ValueError(f"dataset missing columns: {sorted(missing)}")
        if bars.index.has_duplicates:
            raise ValueError("dataset contains duplicate timestamps")
        return bars.sort_index()

    @staticmethod
    def _prices(
        prepared: Mapping[str, pd.DataFrame],
        timestamp: pd.Timestamp,
    ) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol, bars in prepared.items():
            if timestamp not in bars.index:
                continue
            close_value = bars.at[timestamp, "close"]
            if pd.isna(close_value):
                continue
            prices[symbol] = float(np.asarray(close_value, dtype=float).item())
        return prices

    @staticmethod
    def _atr(bars: pd.DataFrame) -> float:
        history = bars.tail(15)
        previous = history["close"].shift(1)
        ranges = pd.concat(
            [
                history["high"] - history["low"],
                (history["high"] - previous).abs(),
                (history["low"] - previous).abs(),
            ],
            axis=1,
        ).max(axis=1)
        value = float(ranges.tail(14).mean())
        return max(value, float(history["close"].iloc[-1]) * 0.005)

    @staticmethod
    def _slippage(
        asset_class: AssetClass,
        config: RotationConfig,
    ) -> float:
        bps = (
            config.slippage_bps_crypto
            if asset_class == AssetClass.CRYPTO
            else config.slippage_bps_stock
        )
        return bps / 10_000.0

    @staticmethod
    def _metrics(
        initial_cash: float,
        final_cash: float,
        trades: list[RotationTrade],
        equity_curve: list[tuple[datetime, float]],
    ) -> dict[str, float | int]:
        total_return = final_cash / initial_cash - 1.0
        values = np.asarray([value for _, value in equity_curve], dtype=float)

        volatility = 0.0
        sharpe = 0.0
        sortino = 0.0
        max_drawdown = 0.0
        cagr = 0.0
        calmar = 0.0
        exposure_days = 0.0

        if len(values) > 1:
            index = pd.DatetimeIndex([timestamp for timestamp, _ in equity_curve])
            returns = pd.Series(values, index=index).pct_change().dropna()
            standard_deviation = float(returns.std(ddof=0))
            volatility = standard_deviation * np.sqrt(252)
            sharpe = (
                float(returns.mean() / standard_deviation * np.sqrt(252))
                if standard_deviation > 0
                else 0.0
            )
            downside = returns[returns < 0]
            downside_deviation = float(downside.std(ddof=0)) if len(downside) else 0.0
            sortino = (
                float(returns.mean() / downside_deviation * np.sqrt(252))
                if downside_deviation > 0
                else 0.0
            )
            peaks = np.maximum.accumulate(values)
            drawdowns = values / peaks - 1.0
            max_drawdown = float(drawdowns.min())

            elapsed_days = max((index[-1] - index[0]).days, 1)
            years = elapsed_days / 365.25
            cagr = float((final_cash / initial_cash) ** (1.0 / years) - 1.0)
            calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else 0.0

            exposure_days = float(sum(trade.holding_days for trade in trades))
            exposure_days = min(
                exposure_days / max(elapsed_days, 1),
                1.0,
            )

        wins = [trade for trade in trades if trade.net_pnl > 0]
        losses = [trade for trade in trades if trade.net_pnl < 0]
        gross_profit = sum(trade.net_pnl for trade in wins)
        gross_loss = abs(sum(trade.net_pnl for trade in losses))
        average_win = gross_profit / len(wins) if wins else 0.0
        average_loss = gross_loss / len(losses) if losses else 0.0
        win_rate = len(wins) / len(trades) if trades else 0.0
        expectancy = win_rate * average_win - (1.0 - win_rate) * average_loss if trades else 0.0

        return {
            "initial_equity": initial_cash,
            "final_equity": final_cash,
            "total_return": total_return,
            "cagr": cagr,
            "annualized_volatility": volatility,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_drawdown,
            "calmar_ratio": calmar,
            "completed_trades": len(trades),
            "win_rate": win_rate,
            "profit_factor": (
                gross_profit / gross_loss
                if gross_loss > 0
                else (float("inf") if gross_profit > 0 else 0.0)
            ),
            "average_win": average_win,
            "average_loss": average_loss,
            "expectancy_per_trade": expectancy,
            "best_trade": max(
                (trade.net_pnl for trade in trades),
                default=0.0,
            ),
            "worst_trade": min(
                (trade.net_pnl for trade in trades),
                default=0.0,
            ),
            "average_holding_days": (
                sum(trade.holding_days for trade in trades) / len(trades) if trades else 0.0
            ),
            "approximate_exposure": exposure_days,
            "rotation_exits": sum(
                1 for trade in trades if trade.exit_reason == ExitReason.ROTATION
            ),
            "total_costs": sum(trade.costs for trade in trades),
            "net_profit": final_cash - initial_cash,
        }
