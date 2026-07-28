from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.safety import TradingMode
from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderReceipt,
    OrderRequest,
    OrderSnapshot,
)


class BrokerAdapter(Protocol):
    name: str
    mode: TradingMode
    capabilities: BrokerCapabilities

    def submit_order(self, order: OrderRequest) -> OrderReceipt: ...

    def cancel_order(self, order_id: str) -> bool: ...

    def get_order(self, order_id: str) -> OrderSnapshot | None: ...

    def list_orders(self, *, include_terminal: bool = True) -> Sequence[OrderSnapshot]: ...

    def list_fills(self, order_id: str | None = None) -> Sequence[Fill]: ...

    def get_account(self) -> AccountSnapshot: ...
