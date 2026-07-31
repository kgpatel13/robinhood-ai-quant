from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import NoReturn

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.errors import BrokerError, BrokerErrorCategory
from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.brokers.safety import TradingMode
from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderReceipt,
    OrderRequest,
    OrderSnapshot,
    Position,
)
from src.robinhood_crypto.models import BestBidAsk, CryptoHolding
from src.robinhood_crypto.service import RobinhoodCryptoReadService


class RobinhoodCryptoReadOnlyAdapter:
    """Read-only broker adapter backed by the official Robinhood Crypto API.

    All mutation methods intentionally fail closed. Live order support belongs in a
    later phase after order-schema validation, shadow execution, and risk gates.
    """

    name = "robinhood-crypto"
    mode = TradingMode.LIVE
    capabilities = BrokerCapabilities(
        paper_trading=False,
        live_trading=False,
        market_orders=False,
        limit_orders=False,
        order_cancellation=False,
        order_replacement=False,
        fills=False,
    )

    def __init__(self, service: RobinhoodCryptoReadService) -> None:
        self._service = service
        self._connected = False

    def connect(self) -> None:
        account = self._service.get_account()
        if account.status.strip().lower() != "active":
            raise BrokerError(
                f"Robinhood Crypto account is not active: {account.status or 'unknown'}",
                category=BrokerErrorCategory.AUTHENTICATION,
            )
        self._connected = True

    def health_check(self) -> BrokerHealth:
        try:
            account = self._service.get_account()
        except Exception as exc:
            return BrokerHealth(BrokerConnectionStatus.DISCONNECTED, str(exc))
        status = account.status.strip().lower()
        if status == "active":
            self._connected = True
            return BrokerHealth(BrokerConnectionStatus.CONNECTED, "Robinhood Crypto API ready")
        return BrokerHealth(
            BrokerConnectionStatus.DEGRADED,
            f"Robinhood Crypto account status: {status or 'unknown'}",
        )

    def get_account(self) -> AccountSnapshot:
        account = self._service.get_account()
        positions = self.get_positions()
        market_value = sum(position.market_value for position in positions)
        cash = float(account.crypto_buying_power)
        return AccountSnapshot(
            cash=cash,
            equity=cash + market_value,
            buying_power=float(account.crypto_buying_power),
            positions=tuple(positions),
        )

    def get_positions(self) -> tuple[Position, ...]:
        holdings = [holding for holding in self._service.list_holdings() if holding.total_quantity]
        if not holdings:
            return ()
        symbols = [f"{holding.asset_code.upper()}-USD" for holding in holdings]
        quotes = {quote.symbol.upper(): quote for quote in self._service.get_best_bid_ask(symbols)}
        return tuple(
            self._to_position(holding, quotes.get(symbol))
            for holding, symbol in zip(holdings, symbols, strict=True)
        )

    def list_orders(self, *, include_terminal: bool = True) -> Sequence[OrderSnapshot]:
        del include_terminal
        return ()

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        del order_id
        return None

    def list_fills(self, order_id: str | None = None) -> Sequence[Fill]:
        del order_id
        return ()

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        del order
        self._raise_read_only()

    def cancel_order(self, order_id: str) -> bool:
        del order_id
        self._raise_read_only()

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderReceipt:
        del order_id, order
        self._raise_read_only()

    @staticmethod
    def _to_position(holding: CryptoHolding, quote: BestBidAsk | None) -> Position:
        quantity = float(holding.total_quantity)
        average_cost = 0.0
        if holding.total_quantity:
            average_cost = float(holding.cost_basis / holding.total_quantity)
        market_price = RobinhoodCryptoReadOnlyAdapter._midpoint(quote)
        return Position(
            symbol=f"{holding.asset_code.upper()}-USD",
            quantity=quantity,
            average_cost=average_cost,
            market_price=market_price,
        )

    @staticmethod
    def _midpoint(quote: BestBidAsk | None) -> float:
        if quote is None:
            return 0.0
        two = Decimal("2")
        return float((quote.bid_price + quote.ask_price) / two)

    @staticmethod
    def _raise_read_only() -> NoReturn:
        raise BrokerError(
            "Robinhood Crypto adapter is read-only; live order mutation is disabled",
            category=BrokerErrorCategory.SAFETY_BLOCK,
        )
