from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from src.execution.models import (
    AccountSnapshot,
    Fill,
    OrderReceipt,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
    OrderType,
    Position,
)
from src.execution.state_machine import OrderStateMachine

PriceProvider = Callable[[str], float]


@dataclass
class _Holding:
    quantity: float
    average_cost: float


class PaperBroker:
    name = "paper"

    def __init__(
        self,
        *,
        initial_cash: float = 100_000.0,
        price_provider: PriceProvider,
        commission_per_order: float = 0.0,
        slippage_bps: float = 0.0,
        allow_fractional: bool = True,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if commission_per_order < 0 or slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")
        self._cash = initial_cash
        self._price_provider = price_provider
        self._commission = commission_per_order
        self._slippage_bps = slippage_bps
        self._allow_fractional = allow_fractional
        self._orders: dict[str, OrderSnapshot] = {}
        self._by_client_id: dict[str, str] = {}
        self._fills: list[Fill] = []
        self._holdings: dict[str, _Holding] = {}
        self._lock = RLock()

    def submit_order(self, order: OrderRequest) -> OrderReceipt:
        with self._lock:
            existing_id = self._by_client_id.get(order.client_order_id)
            if existing_id is not None:
                return OrderReceipt(
                    order_id=existing_id,
                    accepted=True,
                    message="duplicate client_order_id returned existing order",
                    client_order_id=order.client_order_id,
                )
            if not self._allow_fractional and not order.quantity.is_integer():
                return self._reject(order, "fractional quantities are disabled")

            order_id = uuid4().hex
            snapshot = OrderSnapshot(order_id=order_id, request=order, status=OrderStatus.CREATED)
            snapshot = OrderStateMachine.transition(snapshot, OrderStatus.SUBMITTED)
            snapshot = OrderStateMachine.transition(snapshot, OrderStatus.ACCEPTED)
            self._orders[order_id] = snapshot
            self._by_client_id[order.client_order_id] = order_id

            market_price = float(self._price_provider(order.symbol))
            if market_price <= 0:
                self._orders[order_id] = OrderStateMachine.transition(
                    snapshot, OrderStatus.REJECTED, message="invalid market price"
                )
                return OrderReceipt(order_id, False, "invalid market price", order.client_order_id)
            if order.order_type is OrderType.LIMIT and not self._is_marketable(order, market_price):
                return OrderReceipt(order_id, True, "accepted and resting", order.client_order_id)

            accepted, message = self._fill(snapshot, market_price)
            return OrderReceipt(order_id, accepted, message, order.client_order_id)

    def _reject(self, order: OrderRequest, message: str) -> OrderReceipt:
        order_id = uuid4().hex
        snapshot = OrderSnapshot(order_id=order_id, request=order, status=OrderStatus.CREATED)
        snapshot = OrderStateMachine.transition(snapshot, OrderStatus.REJECTED, message=message)
        self._orders[order_id] = snapshot
        self._by_client_id[order.client_order_id] = order_id
        return OrderReceipt(order_id, False, message, order.client_order_id)

    @staticmethod
    def _is_marketable(order: OrderRequest, market_price: float) -> bool:
        assert order.limit_price is not None
        if order.side is OrderSide.BUY:
            return market_price <= order.limit_price
        return market_price >= order.limit_price

    def process_open_orders(self) -> int:
        filled = 0
        with self._lock:
            for snapshot in list(self._orders.values()):
                if snapshot.status not in {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}:
                    continue
                price = float(self._price_provider(snapshot.request.symbol))
                if snapshot.request.order_type is OrderType.LIMIT and not self._is_marketable(
                    snapshot.request, price
                ):
                    continue
                accepted, _ = self._fill(snapshot, price)
                filled += int(accepted)
        return filled

    def _fill(self, snapshot: OrderSnapshot, market_price: float) -> tuple[bool, str]:
        order = snapshot.request
        slip = self._slippage_bps / 10_000.0
        execution_price = market_price * (1 + slip if order.side is OrderSide.BUY else 1 - slip)
        quantity = snapshot.remaining_quantity
        notional = execution_price * quantity

        if order.side is OrderSide.BUY:
            total_cost = notional + self._commission
            if total_cost > self._cash + 1e-9:
                self._orders[snapshot.order_id] = OrderStateMachine.transition(
                    snapshot, OrderStatus.REJECTED, message="insufficient buying power"
                )
                return False, "insufficient buying power"
            self._cash -= total_cost
            holding = self._holdings.get(order.symbol, _Holding(0.0, 0.0))
            new_quantity = holding.quantity + quantity
            new_average = (
                holding.quantity * holding.average_cost
                + quantity * execution_price
                ) / new_quantity
            self._holdings[order.symbol] = _Holding(new_quantity, new_average)
        else:
            existing_holding = self._holdings.get(order.symbol)
            if existing_holding is None or existing_holding.quantity + 1e-9 < quantity:
                self._orders[snapshot.order_id] = OrderStateMachine.transition(
                    snapshot, OrderStatus.REJECTED, message="insufficient position"
                )
                return False, "insufficient position"
            self._cash += notional - self._commission
            remaining = existing_holding.quantity - quantity
            if remaining <= 1e-9:
                del self._holdings[order.symbol]
            else:
                self._holdings[order.symbol] = _Holding(
                    remaining, existing_holding.average_cost
                )

        fill = Fill(
            fill_id=uuid4().hex,
            order_id=snapshot.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=execution_price,
            commission=self._commission,
        )
        self._fills.append(fill)
        self._orders[snapshot.order_id] = OrderStateMachine.transition(
            snapshot,
            OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=execution_price,
            message="filled",
        )
        return True, "filled"

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            snapshot = self._orders.get(order_id)
            if snapshot is None or snapshot.terminal:
                return False
            pending = OrderStateMachine.transition(snapshot, OrderStatus.CANCEL_PENDING)
            self._orders[order_id] = OrderStateMachine.transition(pending, OrderStatus.CANCELLED)
            return True

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        return self._orders.get(order_id)

    def list_orders(self, *, include_terminal: bool = True) -> Sequence[OrderSnapshot]:
        orders = tuple(self._orders.values())
        if include_terminal:
            return orders
        return tuple(order for order in orders if not order.terminal)

    def list_fills(self, order_id: str | None = None) -> Sequence[Fill]:
        if order_id is None:
            return tuple(self._fills)
        return tuple(fill for fill in self._fills if fill.order_id == order_id)

    def get_account(self) -> AccountSnapshot:
        positions: list[Position] = []
        market_value = 0.0
        for symbol, holding in sorted(self._holdings.items()):
            price = float(self._price_provider(symbol))
            position = Position(symbol, holding.quantity, holding.average_cost, price)
            positions.append(position)
            market_value += position.market_value
        equity = self._cash + market_value
        return AccountSnapshot(
            cash=self._cash,
            equity=equity,
            buying_power=self._cash,
            positions=tuple(positions),
        )
