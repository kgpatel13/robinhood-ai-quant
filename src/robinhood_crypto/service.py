from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from src.robinhood_crypto.client import RobinhoodCryptoClient
from src.robinhood_crypto.endpoints import RobinhoodCryptoEndpoints
from src.robinhood_crypto.models import (
    BestBidAsk,
    CryptoAccount,
    CryptoHolding,
    CryptoOrder,
    EstimatedPrice,
    JsonObject,
    TradingPair,
)

T = TypeVar("T")


class RobinhoodCryptoReadService:
    """Typed, read-only access to Robinhood Crypto account and market data."""

    def __init__(
        self,
        client: RobinhoodCryptoClient,
        *,
        endpoints: RobinhoodCryptoEndpoints | None = None,
    ) -> None:
        self._client = client
        self._endpoints = endpoints or RobinhoodCryptoEndpoints()

    def get_account(self) -> CryptoAccount:
        payload = self._client.get(self._endpoints.account)
        return CryptoAccount.from_api(self._unwrap_single(payload))

    def list_holdings(self, *, asset_code: str | None = None) -> list[CryptoHolding]:
        params = {"asset_code": asset_code.strip().upper()} if asset_code else None
        payload = self._client.get(self._endpoints.holdings, params=params)
        return [CryptoHolding.from_api(item) for item in self._items(payload)]

    def list_trading_pairs(self, *, symbols: list[str] | None = None) -> list[TradingPair]:
        params: Mapping[str, str] | None = None
        if symbols:
            normalized = [self._normalize_symbol(symbol) for symbol in symbols]
            params = {"symbol": ",".join(normalized)}
        payload = self._client.get(self._endpoints.trading_pairs, params=params)
        return [TradingPair.from_api(item) for item in self._items(payload)]

    def get_best_bid_ask(self, symbols: list[str]) -> list[BestBidAsk]:
        if not symbols:
            raise ValueError("at least one symbol is required")
        params = {"symbol": ",".join(self._normalize_symbol(symbol) for symbol in symbols)}
        payload = self._client.get(self._endpoints.best_bid_ask, params=params)
        return [BestBidAsk.from_api(item) for item in self._items(payload)]

    def get_estimated_price(
        self,
        *,
        symbol: str,
        side: str,
        quantity: str,
    ) -> EstimatedPrice:
        normalized_side = side.strip().lower()
        if normalized_side not in {"bid", "ask"}:
            raise ValueError("side must be 'bid' or 'ask'")
        if not quantity.strip():
            raise ValueError("quantity is required")
        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._client.get(
            self._endpoints.estimated_price,
            params={
                "symbol": normalized_symbol,
                "side": normalized_side,
                "quantity": quantity.strip(),
            },
        )
        item = self._unwrap_single(payload)
        return EstimatedPrice.from_api(
            item,
            symbol=normalized_symbol,
            side=normalized_side,
        )

    def list_orders(self) -> list[CryptoOrder]:
        payload = self._client.get(self._endpoints.orders)
        return [CryptoOrder.from_api(item) for item in self._items(payload)]

    def get_order(self, client_order_id: str) -> CryptoOrder:
        payload = self._client.get(self._endpoints.order(client_order_id))
        return CryptoOrder.from_api(self._unwrap_single(payload))

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if "-" not in normalized:
            normalized = f"{normalized}-USD"
        return normalized

    @staticmethod
    def _items(payload: JsonObject) -> list[JsonObject]:
        raw_items: Any = payload.get("results", payload.get("data", payload))
        if isinstance(raw_items, dict):
            for key in ("results", "items", "orders", "holdings", "trading_pairs"):
                nested = raw_items.get(key)
                if isinstance(nested, list):
                    raw_items = nested
                    break
        if isinstance(raw_items, list):
            items: list[JsonObject] = []
            for item in raw_items:
                if not isinstance(item, dict):
                    raise RuntimeError("Robinhood Crypto list response contains a non-object item")
                items.append(item)
            return items
        if isinstance(raw_items, dict):
            return [raw_items]
        raise RuntimeError("Robinhood Crypto response does not contain object results")

    @classmethod
    def _unwrap_single(cls, payload: JsonObject) -> JsonObject:
        items = cls._items(payload)
        if len(items) != 1:
            raise RuntimeError(f"expected exactly one result, received {len(items)}")
        return items[0]
