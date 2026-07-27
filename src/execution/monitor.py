from __future__ import annotations

from dataclasses import dataclass

from src.execution.broker import Broker
from src.execution.models import OrderSnapshot, OrderStatus


@dataclass(frozen=True)
class ExecutionSummary:
    total_orders: int
    open_orders: int
    filled_orders: int
    rejected_orders: int
    cancelled_orders: int


class ExecutionMonitor:
    def __init__(self, broker: Broker) -> None:
        self._broker = broker

    def open_orders(self) -> tuple[OrderSnapshot, ...]:
        return tuple(self._broker.list_orders(include_terminal=False))

    def summary(self) -> ExecutionSummary:
        orders = tuple(self._broker.list_orders())
        return ExecutionSummary(
            total_orders=len(orders),
            open_orders=sum(not order.terminal for order in orders),
            filled_orders=sum(order.status is OrderStatus.FILLED for order in orders),
            rejected_orders=sum(order.status is OrderStatus.REJECTED for order in orders),
            cancelled_orders=sum(order.status is OrderStatus.CANCELLED for order in orders),
        )
