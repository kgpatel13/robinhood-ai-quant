from __future__ import annotations

from collections import Counter

from src.brokers.base import BrokerAdapter
from src.execution.models import OrderSnapshot
from src.live_execution.idempotency import IdempotencyRegistry
from src.live_execution.models import RecoveryReport


class ExecutionRecoveryManager:
    def __init__(self, broker: BrokerAdapter, idempotency: IdempotencyRegistry) -> None:
        self._broker = broker
        self._idempotency = idempotency

    def recover(self) -> RecoveryReport:
        orders = tuple(self._broker.list_orders(include_terminal=True))
        counts = Counter(order.request.client_order_id for order in orders)
        duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
        for order in orders:
            self._idempotency.reserve(order.request.client_order_id)
        active = tuple(order.order_id for order in orders if not order.terminal)
        return RecoveryReport(orders, active, duplicates)

    @staticmethod
    def nonterminal(orders: tuple[OrderSnapshot, ...]) -> tuple[OrderSnapshot, ...]:
        return tuple(order for order in orders if not order.terminal)
