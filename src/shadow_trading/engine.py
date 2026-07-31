from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from src.execution.models import Fill, OrderReceipt, OrderRequest, OrderSide, OrderStatus
from src.trading_ledger.sqlite import SQLiteTradingLedger

QuoteProvider = Callable[[str], float]
RiskGate = Callable[[OrderRequest, float], tuple[bool, str]]


@dataclass(frozen=True, slots=True)
class ShadowExecutionConfig:
    slippage_bps: float = 5.0
    commission_per_order: float = 0.0
    max_order_notional: float = 10_000.0

    def __post_init__(self) -> None:
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps cannot be negative")
        if self.commission_per_order < 0:
            raise ValueError("commission_per_order cannot be negative")
        if self.max_order_notional <= 0:
            raise ValueError("max_order_notional must be positive")


class ShadowExecutionEngine:
    """Executes simulated fills from live quotes and persists every event."""

    def __init__(
        self,
        *,
        ledger: SQLiteTradingLedger,
        quote_provider: QuoteProvider,
        config: ShadowExecutionConfig | None = None,
        risk_gate: RiskGate | None = None,
    ) -> None:
        self._ledger = ledger
        self._quote_provider = quote_provider
        self._config = config or ShadowExecutionConfig()
        self._risk_gate = risk_gate

    def submit(self, order: OrderRequest, *, strategy: str = "unknown") -> OrderReceipt:
        reference_price = float(self._quote_provider(order.symbol))
        if reference_price <= 0:
            raise ValueError(f"invalid quote for {order.symbol}: {reference_price}")

        order_id = f"shadow-{uuid4().hex}"
        notional = reference_price * order.quantity
        if notional > self._config.max_order_notional:
            message = (
                f"order notional {notional:.2f} exceeds shadow limit "
                f"{self._config.max_order_notional:.2f}"
            )
            self._ledger.record_order(
                order_id=order_id,
                request=order,
                status=OrderStatus.REJECTED.value,
                strategy=strategy,
                message=message,
            )
            self._ledger.record_risk_event(
                code="MAX_ORDER_NOTIONAL",
                severity="warning",
                message=message,
                context={"symbol": order.symbol, "notional": notional},
            )
            return OrderReceipt(order_id, False, message, order.client_order_id)

        if self._risk_gate is not None:
            allowed, message = self._risk_gate(order, reference_price)
            if not allowed:
                self._ledger.record_order(
                    order_id=order_id,
                    request=order,
                    status=OrderStatus.REJECTED.value,
                    strategy=strategy,
                    message=message,
                )
                self._ledger.record_risk_event(
                    code="RISK_GATE_REJECTED",
                    severity="warning",
                    message=message,
                    context={"symbol": order.symbol},
                )
                return OrderReceipt(order_id, False, message, order.client_order_id)

        current_positions = {position.symbol: position for position in self._ledger.positions()}
        if order.side is OrderSide.SELL:
            available = current_positions.get(order.symbol)
            if available is None or available.quantity + 1e-12 < order.quantity:
                message = "shadow sell rejected: insufficient position"
                self._ledger.record_order(
                    order_id=order_id,
                    request=order,
                    status=OrderStatus.REJECTED.value,
                    strategy=strategy,
                    message=message,
                )
                return OrderReceipt(order_id, False, message, order.client_order_id)

        slippage = self._config.slippage_bps / 10_000.0
        fill_price = (
            reference_price * (1.0 + slippage)
            if order.side is OrderSide.BUY
            else reference_price * (1.0 - slippage)
        )
        if order.side is OrderSide.BUY:
            required_cash = fill_price * order.quantity + self._config.commission_per_order
            if required_cash > self._ledger.summary().cash + 1e-12:
                message = "shadow buy rejected: insufficient cash"
                self._ledger.record_order(
                    order_id=order_id,
                    request=order,
                    status=OrderStatus.REJECTED.value,
                    strategy=strategy,
                    message=message,
                )
                return OrderReceipt(order_id, False, message, order.client_order_id)

        self._ledger.record_order(
            order_id=order_id,
            request=order,
            status=OrderStatus.FILLED.value,
            strategy=strategy,
            message="shadow fill",
        )
        self._ledger.record_fill(
            Fill(
                fill_id=f"fill-{uuid4().hex}",
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=self._config.commission_per_order,
            )
        )
        return OrderReceipt(order_id, True, "shadow fill", order.client_order_id)
