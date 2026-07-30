from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

JsonObject = dict[str, Any]


def _decimal(value: Any, *, field: str, default: str = "0") -> Decimal:
    candidate = default if value is None else value
    try:
        return Decimal(str(candidate))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _text(value: Any, *, field: str, required: bool = False) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise ValueError(f"{field} is required")
    return text


@dataclass(frozen=True, slots=True)
class CryptoAccount:
    account_number: str
    status: str
    buying_power: Decimal
    crypto_buying_power: Decimal

    @classmethod
    def from_api(cls, payload: JsonObject) -> CryptoAccount:
        return cls(
            account_number=_text(payload.get("account_number"), field="account_number"),
            status=_text(payload.get("status"), field="status"),
            buying_power=_decimal(payload.get("buying_power"), field="buying_power"),
            crypto_buying_power=_decimal(
                payload.get("crypto_buying_power", payload.get("buying_power")),
                field="crypto_buying_power",
            ),
        )


@dataclass(frozen=True, slots=True)
class CryptoHolding:
    asset_code: str
    total_quantity: Decimal
    quantity_available_for_trading: Decimal
    cost_basis: Decimal

    @classmethod
    def from_api(cls, payload: JsonObject) -> CryptoHolding:
        return cls(
            asset_code=_text(payload.get("asset_code"), field="asset_code", required=True),
            total_quantity=_decimal(payload.get("total_quantity"), field="total_quantity"),
            quantity_available_for_trading=_decimal(
                payload.get("quantity_available_for_trading"),
                field="quantity_available_for_trading",
            ),
            cost_basis=_decimal(payload.get("cost_basis"), field="cost_basis"),
        )


@dataclass(frozen=True, slots=True)
class TradingPair:
    symbol: str
    asset_code: str
    quote_currency_code: str
    status: str
    tradable: bool
    min_order_size: Decimal
    max_order_size: Decimal | None

    @classmethod
    def from_api(cls, payload: JsonObject) -> TradingPair:
        max_order_raw = payload.get("max_order_size")
        return cls(
            symbol=_text(payload.get("symbol"), field="symbol", required=True),
            asset_code=_text(payload.get("asset_code"), field="asset_code"),
            quote_currency_code=_text(
                payload.get("quote_currency_code"), field="quote_currency_code"
            ),
            status=_text(payload.get("status"), field="status"),
            tradable=bool(payload.get("tradable", payload.get("status") == "active")),
            min_order_size=_decimal(
                payload.get("min_order_size"), field="min_order_size", default="0"
            ),
            max_order_size=(
                None
                if max_order_raw in (None, "")
                else _decimal(max_order_raw, field="max_order_size")
            ),
        )


@dataclass(frozen=True, slots=True)
class BestBidAsk:
    symbol: str
    bid_price: Decimal
    ask_price: Decimal
    timestamp: str

    @classmethod
    def from_api(cls, payload: JsonObject) -> BestBidAsk:
        return cls(
            symbol=_text(payload.get("symbol"), field="symbol", required=True),
            bid_price=_decimal(payload.get("bid_inclusive_of_sell_spread"), field="bid_price"),
            ask_price=_decimal(payload.get("ask_inclusive_of_buy_spread"), field="ask_price"),
            timestamp=_text(payload.get("timestamp"), field="timestamp"),
        )


@dataclass(frozen=True, slots=True)
class EstimatedPrice:
    symbol: str
    side: str
    quantity: Decimal
    total_notional: Decimal
    estimated_unit_price: Decimal

    @classmethod
    def from_api(cls, payload: JsonObject, *, symbol: str, side: str) -> EstimatedPrice:
        quantity = _decimal(payload.get("quantity"), field="quantity")
        total_notional = _decimal(
            payload.get("total_inclusive_of_spread", payload.get("total_notional")),
            field="total_notional",
        )
        unit_price = _decimal(
            payload.get("estimated_unit_price", payload.get("price")),
            field="estimated_unit_price",
            default=(str(total_notional / quantity) if quantity else "0"),
        )
        return cls(
            symbol=symbol,
            side=side,
            quantity=quantity,
            total_notional=total_notional,
            estimated_unit_price=unit_price,
        )


@dataclass(frozen=True, slots=True)
class CryptoOrder:
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    state: str
    quantity: Decimal
    average_price: Decimal
    created_at: str
    updated_at: str

    @classmethod
    def from_api(cls, payload: JsonObject) -> CryptoOrder:
        configuration = (
            payload.get("market_order_config") or payload.get("limit_order_config") or {}
        )
        if not isinstance(configuration, dict):
            configuration = {}
        quantity = configuration.get("asset_quantity", payload.get("asset_quantity"))
        return cls(
            client_order_id=_text(
                payload.get("client_order_id"), field="client_order_id", required=True
            ),
            symbol=_text(payload.get("symbol"), field="symbol"),
            side=_text(payload.get("side"), field="side"),
            order_type=_text(payload.get("type"), field="type"),
            state=_text(payload.get("state"), field="state"),
            quantity=_decimal(quantity, field="quantity"),
            average_price=_decimal(
                payload.get("average_price"), field="average_price", default="0"
            ),
            created_at=_text(payload.get("created_at"), field="created_at"),
            updated_at=_text(payload.get("updated_at"), field="updated_at"),
        )
