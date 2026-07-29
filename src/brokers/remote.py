from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from src.execution.models import AccountSnapshot, Fill, OrderRequest, OrderSnapshot


class BrokerTransport(Protocol):
    """Transport boundary for official SDKs or HTTP clients.

    Concrete transports own authentication and network behavior. Adapters only
    normalize broker data into Atlas execution models.
    """

    def connect(self) -> None: ...

    def health_check(self) -> Mapping[str, object]: ...

    def get_account(self) -> AccountSnapshot: ...

    def get_orders(self) -> Sequence[OrderSnapshot]: ...

    def get_fills(self, order_id: str | None = None) -> Sequence[Fill]: ...

    def submit_order(self, order: OrderRequest) -> OrderSnapshot: ...

    def cancel_order(self, order_id: str) -> bool: ...

    def replace_order(self, order_id: str, order: OrderRequest) -> OrderSnapshot: ...
