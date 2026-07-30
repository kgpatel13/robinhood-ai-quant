from __future__ import annotations

from collections.abc import Sequence

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.errors import BrokerError, BrokerErrorCategory
from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.brokers.remote import BrokerTransport
from src.brokers.safety import TradingMode, TradingSafetyPolicy
from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderReceipt,
    OrderRequest,
    OrderSnapshot,
    Position,
)


class GuardedExternalBrokerAdapter:
    """Broker-neutral adapter with a hard live-trading safety boundary."""

    name = "external"
    mode = TradingMode.PAPER
    capabilities = BrokerCapabilities(paper_trading=True)

    def __init__(
        self,
        transport: BrokerTransport,
        *,
        mode: TradingMode = TradingMode.PAPER,
        safety_policy: TradingSafetyPolicy | None = None,
    ) -> None:
        self._transport = transport
        self.mode = mode
        self._safety = safety_policy or TradingSafetyPolicy()
        self._connected = False

    def connect(self) -> None:
        self._transport.connect()
        self._connected = True

    def health_check(self) -> BrokerHealth:
        if not self._connected:
            return BrokerHealth(BrokerConnectionStatus.DISCONNECTED, "adapter is not connected")
        try:
            payload = self._transport.health_check()
        except Exception as exc:
            return BrokerHealth(BrokerConnectionStatus.DEGRADED, str(exc))
        healthy = bool(payload.get("healthy", True))
        status = BrokerConnectionStatus.CONNECTED if healthy else BrokerConnectionStatus.DEGRADED
        return BrokerHealth(status, str(payload.get("message", "")))

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        self._validate_ready()
        snapshot = self._transport.submit_order(order)
        return OrderReceipt(
            order_id=snapshot.order_id,
            accepted=not snapshot.terminal or snapshot.filled_quantity > 0,
            message=snapshot.message,
            client_order_id=order.client_order_id,
        )

    def cancel_order(self, order_id: str) -> bool:
        self._validate_ready()
        return self._transport.cancel_order(order_id)

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderReceipt:
        self._validate_ready()
        self.capabilities.require("order_replacement")
        snapshot = self._transport.replace_order(order_id, order)
        return OrderReceipt(
            order_id=snapshot.order_id,
            accepted=True,
            message=snapshot.message,
            client_order_id=order.client_order_id,
        )

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        return next((item for item in self.list_orders() if item.order_id == order_id), None)

    def list_orders(self, *, include_terminal: bool = True) -> Sequence[OrderSnapshot]:
        self._require_connected()
        orders = tuple(self._transport.get_orders())
        if include_terminal:
            return orders
        return tuple(order for order in orders if not order.terminal)

    def list_fills(self, order_id: str | None = None) -> Sequence[Fill]:
        self._require_connected()
        return tuple(self._transport.get_fills(order_id))

    def get_account(self) -> AccountSnapshot:
        self._require_connected()
        return self._transport.get_account()

    def get_positions(self) -> tuple[Position, ...]:
        return tuple(self.get_account().positions)

    def _validate_ready(self) -> None:
        self._require_connected()
        self._safety.validate(
            self.mode,
            adapter_supports_live=self.capabilities.live_trading,
        )

    def _require_connected(self) -> None:
        if not self._connected:
            raise BrokerError(
                "broker adapter is not connected",
                category=BrokerErrorCategory.CONNECTION,
                retryable=True,
            )
