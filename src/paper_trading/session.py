from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from src.paper_trading.broker import PaperBroker
from src.paper_trading.feed import MarketDataFeed
from src.paper_trading.models import MarketQuote, PaperOrderResult
from src.paper_trading.persistence import PaperAccountStore


class SessionStatus(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    HALTED = "halted"


@dataclass(frozen=True)
class PaperSessionConfig:
    symbols: tuple[str, ...]
    timezone: str = "America/New_York"
    market_open: time = time(9, 30)
    flatten_time: time = time(15, 55)
    market_close: time = time(16, 0)
    stale_quote_seconds: int = 180


@dataclass(frozen=True)
class PaperSessionSnapshot:
    status: SessionStatus
    as_of: datetime
    quotes: dict[str, MarketQuote]
    equity: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int
    order_count: int
    messages: tuple[str, ...]


class RealMarketPaperSession:
    def __init__(
        self,
        config: PaperSessionConfig,
        feed: MarketDataFeed,
        broker: PaperBroker,
        store: PaperAccountStore,
    ) -> None:
        self.config = config
        self.feed = feed
        self.broker = broker
        self.store = store
        self.status = SessionStatus.STOPPED
        self.messages: list[str] = []

    def start(self) -> None:
        if self.status != SessionStatus.HALTED:
            self.status = SessionStatus.RUNNING
            self.messages.append("paper session started")

    def pause(self) -> None:
        if self.status == SessionStatus.RUNNING:
            self.status = SessionStatus.PAUSED
            self.messages.append("paper session paused")

    def resume(self) -> None:
        if self.status == SessionStatus.PAUSED:
            self.status = SessionStatus.RUNNING
            self.messages.append("paper session resumed")

    def stop(self) -> None:
        self.status = SessionStatus.STOPPED
        self.store.save(self.broker.account)
        self.messages.append("paper session stopped")

    def halt(self, reason: str) -> None:
        self.status = SessionStatus.HALTED
        self.store.save(self.broker.account)
        self.messages.append(f"session halted: {reason}")

    def cycle(self, now: datetime | None = None) -> PaperSessionSnapshot:
        as_of = now or datetime.now(UTC)
        quotes = self.feed.latest_quotes(self.config.symbols)
        self._validate_quotes(quotes, as_of)
        self.broker.mark_to_market(quotes)
        local_time = as_of.astimezone(ZoneInfo(self.config.timezone)).time()
        if (
            self.status == SessionStatus.RUNNING
            and self.config.flatten_time <= local_time < self.config.market_close
        ):
            fills = self.broker.flatten_all(quotes, as_of)
            if fills:
                self.messages.append(f"end-of-day flatten submitted for {len(fills)} positions")
        self.store.save(self.broker.account)
        return PaperSessionSnapshot(
            status=self.status,
            as_of=as_of,
            quotes=quotes,
            equity=self.broker.account.equity,
            cash=self.broker.account.cash,
            realized_pnl=self.broker.account.realized_pnl,
            unrealized_pnl=self.broker.account.unrealized_pnl,
            open_positions=len(self.broker.account.positions),
            order_count=len(self.broker.account.orders),
            messages=tuple(self.messages[-10:]),
        )

    def flatten(self, now: datetime | None = None) -> list[PaperOrderResult]:
        as_of = now or datetime.now(UTC)
        quotes = self.feed.latest_quotes(self.config.symbols)
        results = self.broker.flatten_all(quotes, as_of)
        self.store.save(self.broker.account)
        return results

    def _validate_quotes(self, quotes: dict[str, MarketQuote], as_of: datetime) -> None:
        missing = sorted(set(self.config.symbols) - set(quotes))
        if missing:
            self.halt(f"missing quotes: {', '.join(missing)}")
            return
        stale = [
            symbol
            for symbol, quote in quotes.items()
            if abs((as_of - quote.timestamp).total_seconds()) > self.config.stale_quote_seconds
        ]
        if stale:
            self.halt(f"stale quotes: {', '.join(sorted(stale))}")
