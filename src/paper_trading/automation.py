from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

import pandas as pd

from src.analytics.performance import EquityJournal, EquitySnapshot
from src.paper_trading.broker import PaperBroker
from src.paper_trading.models import (
    MarketQuote,
    PaperOrderRequest,
    PaperOrderResult,
    PaperOrderSide,
)
from src.paper_trading.persistence import PaperAccountStore
from src.strategies.base import Strategy


class SignalDataProvider(Protocol):
    def bars(self, symbol: str) -> pd.DataFrame: ...


@dataclass(frozen=True)
class AutomatedPaperConfig:
    symbols: tuple[str, ...]
    strategy_name: str
    target_position_fraction: float = 0.05
    maximum_deployed_fraction: float = 0.40
    maximum_open_positions: int = 5
    maximum_trades_per_day: int = 12
    minimum_history: int = 60

    def validate(self) -> None:
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        if not 0 < self.target_position_fraction <= 1:
            raise ValueError("target_position_fraction must be in (0, 1]")
        if not 0 < self.maximum_deployed_fraction <= 1:
            raise ValueError("maximum_deployed_fraction must be in (0, 1]")
        if self.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be positive")
        if self.maximum_trades_per_day < 1:
            raise ValueError("maximum_trades_per_day must be positive")


@dataclass(frozen=True)
class AutomatedCycleResult:
    as_of: datetime
    orders: tuple[PaperOrderResult, ...]
    signals: dict[str, float]
    rejected: dict[str, str]
    equity: float
    open_positions: int


class AutomatedPaperTrader:
    def __init__(
        self,
        config: AutomatedPaperConfig,
        strategy: Strategy,
        data_provider: SignalDataProvider,
        broker: PaperBroker,
        store: PaperAccountStore,
        equity_journal: EquityJournal,
    ) -> None:
        config.validate()
        self.config = config
        self.strategy = strategy
        self.data_provider = data_provider
        self.broker = broker
        self.store = store
        self.equity_journal = equity_journal

    def cycle(
        self,
        quotes: dict[str, MarketQuote],
        now: datetime | None = None,
    ) -> AutomatedCycleResult:
        as_of = now or datetime.now(UTC)
        results: list[PaperOrderResult] = []
        signals: dict[str, float] = {}
        rejected: dict[str, str] = {}
        filled_today = sum(
            1
            for item in self.broker.account.orders
            if item.fill is not None and item.fill.timestamp.date() == as_of.date()
        )
        for symbol in self.config.symbols:
            quote = quotes.get(symbol)
            if quote is None:
                rejected[symbol] = "missing quote"
                continue
            try:
                bars = self.data_provider.bars(symbol)
            except Exception as exc:
                rejected[symbol] = f"signal data unavailable: {exc}"
                continue
            required_history = max(
                self.config.minimum_history, self.strategy.metadata.required_history
            )
            if len(bars) < required_history:
                rejected[symbol] = "insufficient signal history"
                continue
            signal_series = self.strategy.generate_signals(bars)
            target = float(signal_series.iloc[-1])
            signals[symbol] = target
            position = self.broker.account.positions.get(symbol)
            if target > 0 and position is None:
                reason = self._entry_rejection_reason(filled_today)
                if reason is not None:
                    rejected[symbol] = reason
                    continue
                quantity = int(
                    self.broker.account.equity
                    * self.config.target_position_fraction
                    / max(quote.ask, 0.01)
                )
                if quantity < 1:
                    rejected[symbol] = "target allocation is below one share"
                    continue
                request = self._request(symbol, PaperOrderSide.BUY, quantity, as_of)
                result = self.broker.submit(request, quote)
                results.append(result)
                if result.fill is not None:
                    filled_today += 1
            elif target <= 0 and position is not None:
                request = self._request(symbol, PaperOrderSide.SELL, position.quantity, as_of)
                result = self.broker.submit(request, quote)
                results.append(result)
                if result.fill is not None:
                    filled_today += 1
        self.broker.mark_to_market(quotes)
        self.store.save(self.broker.account)
        self.equity_journal.append(
            EquitySnapshot(
                timestamp=as_of,
                equity=self.broker.account.equity,
                cash=self.broker.account.cash,
                market_value=self.broker.account.market_value,
                realized_pnl=self.broker.account.realized_pnl,
                unrealized_pnl=self.broker.account.unrealized_pnl,
                open_positions=len(self.broker.account.positions),
            )
        )
        return AutomatedCycleResult(
            as_of=as_of,
            orders=tuple(results),
            signals=signals,
            rejected=rejected,
            equity=self.broker.account.equity,
            open_positions=len(self.broker.account.positions),
        )

    def _entry_rejection_reason(self, filled_today: int) -> str | None:
        account = self.broker.account
        if filled_today >= self.config.maximum_trades_per_day:
            return "maximum trades per day reached"
        if len(account.positions) >= self.config.maximum_open_positions:
            return "maximum open positions reached"
        deployed_fraction = account.market_value / account.equity if account.equity else 1.0
        proposed_fraction = deployed_fraction + self.config.target_position_fraction
        if proposed_fraction > self.config.maximum_deployed_fraction:
            return "maximum deployed capital reached"
        return None

    def _request(
        self,
        symbol: str,
        side: PaperOrderSide,
        quantity: int,
        as_of: datetime,
    ) -> PaperOrderRequest:
        raw_id = (
            f"{self.config.strategy_name}|{symbol}|{side.value}|{quantity}|"
            f"{as_of.astimezone(UTC).isoformat()}"
        )
        order_id = sha256(raw_id.encode("utf-8")).hexdigest()[:24]
        return PaperOrderRequest(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            submitted_at=as_of,
            strategy=self.config.strategy_name,
        )
