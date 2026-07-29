from __future__ import annotations

from collections.abc import Sequence

from src.brokers.audit import BrokerAuditLog
from src.brokers.capabilities import BrokerCapabilities
from src.brokers.errors import BrokerError, BrokerErrorCategory
from src.brokers.models import BrokerConnectionStatus, BrokerHealth
from src.brokers.safety import TradingMode, TradingSafetyPolicy
from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderReceipt,
    OrderRequest,
    OrderSnapshot,
    Position,
)
from src.execution.paper import PaperBroker


class PaperBrokerAdapter:
    """Audited adapter around the existing deterministic paper broker."""

    name = "atlas-paper"
    mode = TradingMode.PAPER
    capabilities = BrokerCapabilities(paper_trading=True, live_trading=False)

    def __init__(
        self,
        broker: PaperBroker,
        *,
        audit_log: BrokerAuditLog | None = None,
        safety_policy: TradingSafetyPolicy | None = None,
    ) -> None:
        self._broker = broker
        self._audit = audit_log
        self._safety = safety_policy or TradingSafetyPolicy()

    def connect(self) -> None:
        return None

    def health_check(self) -> BrokerHealth:
        return BrokerHealth(BrokerConnectionStatus.CONNECTED, "paper broker ready")

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        self._safety.validate(self.mode, adapter_supports_live=self.capabilities.live_trading)
        receipt = self._broker.submit_order(order)
        self._record(
            "order_submitted",
            receipt.order_id or order.client_order_id,
            {
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "accepted": receipt.accepted,
                "message": receipt.message,
            },
        )
        return receipt

    def cancel_order(self, order_id: str) -> bool:
        result = self._broker.cancel_order(order_id)
        self._record("order_cancelled", order_id, {"cancelled": result})
        return result

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderReceipt:
        raise BrokerError(
            "paper adapter does not support order replacement",
            category=BrokerErrorCategory.UNSUPPORTED,
        )

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        return self._broker.get_order(order_id)

    def list_orders(self, *, include_terminal: bool = True) -> Sequence[OrderSnapshot]:
        return self._broker.list_orders(include_terminal=include_terminal)

    def list_fills(self, order_id: str | None = None) -> Sequence[Fill]:
        return self._broker.list_fills(order_id)

    def get_positions(self) -> tuple[Position, ...]:
        return tuple(self.get_account().positions)

    def get_account(self) -> AccountSnapshot:
        account = self._broker.get_account()
        self._record(
            "account_snapshot",
            self.name,
            {"cash": account.cash, "equity": account.equity, "buying_power": account.buying_power},
        )
        return account

    def _record(self, event_type: str, entity_id: str, payload: dict[str, object]) -> None:
        if self._audit is not None:
            self._audit.append(
                event_type=event_type,
                broker=self.name,
                entity_id=entity_id,
                payload=payload,
            )
