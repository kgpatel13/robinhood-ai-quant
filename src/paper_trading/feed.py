from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import pandas as pd

from src.paper_trading.models import MarketQuote


class MarketDataFeed(Protocol):
    def latest_quotes(self, symbols: tuple[str, ...]) -> dict[str, MarketQuote]: ...


@dataclass(frozen=True)
class YahooMarketDataFeed:
    spread_bps: float = 2.0

    def latest_quotes(self, symbols: tuple[str, ...]) -> dict[str, MarketQuote]:
        import yfinance as yf

        quotes: dict[str, MarketQuote] = {}
        for symbol in symbols:
            frame = yf.download(
                symbol,
                period="1d",
                interval="1m",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if frame.empty:
                continue
            close = frame["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            last = float(close.dropna().iloc[-1])
            half_spread = last * self.spread_bps / 20_000.0
            quotes[symbol] = MarketQuote(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bid=last - half_spread,
                ask=last + half_spread,
                last=last,
                source="yahoo",
            )
        return quotes


@dataclass
class StaticMarketDataFeed:
    quotes: dict[str, MarketQuote]

    def latest_quotes(self, symbols: tuple[str, ...]) -> dict[str, MarketQuote]:
        return {symbol: self.quotes[symbol] for symbol in symbols if symbol in self.quotes}
