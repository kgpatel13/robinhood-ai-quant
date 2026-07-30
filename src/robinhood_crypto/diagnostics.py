from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.robinhood_crypto.service import RobinhoodCryptoReadService


class RobinhoodCryptoDiagnostics:
    """Produces sanitized connectivity diagnostics without exposing balances or identifiers."""

    def __init__(self, service: RobinhoodCryptoReadService) -> None:
        self._service = service

    def run(self, *, quote_symbols: list[str] | None = None) -> dict[str, Any]:
        account = self._service.get_account()
        holdings = self._service.list_holdings()
        pairs = self._service.list_trading_pairs(symbols=quote_symbols)
        quotes = self._service.get_best_bid_ask(quote_symbols) if quote_symbols else []
        return {
            "authenticated": True,
            "account_status": account.status,
            "holding_count": len(holdings),
            "trading_pair_count": len(pairs),
            "quote_count": len(quotes),
            "quote_symbols": [quote.symbol for quote in quotes],
            "fields": {
                "account": sorted(asdict(account).keys()),
                "holding": sorted(asdict(holdings[0]).keys()) if holdings else [],
                "trading_pair": sorted(asdict(pairs[0]).keys()) if pairs else [],
                "quote": sorted(asdict(quotes[0]).keys()) if quotes else [],
            },
        }
