from __future__ import annotations

from dataclasses import replace

from src.execution.models import OrderSnapshot, OrderStatus, utc_now

_ALLOWED: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.SUBMITTED, OrderStatus.REJECTED}),
    OrderStatus.SUBMITTED: frozenset({OrderStatus.ACCEPTED, OrderStatus.REJECTED}),
    OrderStatus.ACCEPTED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.CANCEL_PENDING: frozenset({OrderStatus.CANCELLED, OrderStatus.FILLED}),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
}


class InvalidOrderTransition(ValueError):
    pass


class OrderStateMachine:
    @staticmethod
    def transition(
        order: OrderSnapshot,
        status: OrderStatus,
        *,
        filled_quantity: float | None = None,
        average_fill_price: float | None = None,
        message: str | None = None,
    ) -> OrderSnapshot:
        if status not in _ALLOWED[order.status]:
            raise InvalidOrderTransition(f"invalid transition: {order.status} -> {status}")
        new_filled = order.filled_quantity if filled_quantity is None else filled_quantity
        if new_filled < order.filled_quantity or new_filled > order.request.quantity:
            raise InvalidOrderTransition(
                "filled quantity must be monotonic and within order quantity"
            )
        if new_filled > 0 and (average_fill_price is None and order.average_fill_price is None):
            raise InvalidOrderTransition("average fill price is required for filled quantity")
        return replace(
            order,
            status=status,
            filled_quantity=new_filled,
            average_fill_price=(
                order.average_fill_price if average_fill_price is None else average_fill_price
            ),
            message=order.message if message is None else message,
            updated_at=utc_now(),
        )
