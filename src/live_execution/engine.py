from __future__ import annotations

from dataclasses import replace

from src.brokers.base import BrokerAdapter
from src.brokers.safety import TradingMode
from src.execution.models import OrderRequest
from src.live_execution.idempotency import IdempotencyRegistry
from src.live_execution.models import (
    ExecutionContext,
    ExecutionDecision,
    ExecutionPolicy,
    ExecutionResult,
)


class LiveExecutionEngine:
    """Broker-independent order gateway with hard safety and duplicate guards."""

    def __init__(
        self,
        broker: BrokerAdapter,
        *,
        policy: ExecutionPolicy | None = None,
        idempotency: IdempotencyRegistry | None = None,
    ) -> None:
        self._broker = broker
        self._policy = policy or ExecutionPolicy()
        self._idempotency = idempotency or IdempotencyRegistry()

    def submit(self, request: OrderRequest, context: ExecutionContext) -> ExecutionResult:
        blocked = self._block_reason(request, context)
        if blocked:
            return ExecutionResult(ExecutionDecision.BLOCKED, request, message=blocked)

        if not self._idempotency.reserve(request.client_order_id):
            return ExecutionResult(
                ExecutionDecision.DUPLICATE,
                request,
                message="duplicate_client_order_id",
            )

        adjusted = request
        if context.size_multiplier < 1.0:
            adjusted = replace(request, quantity=request.quantity * context.size_multiplier)

        try:
            receipt = self._broker.submit_order(adjusted)
        except Exception as exc:
            self._idempotency.release(request.client_order_id)
            return ExecutionResult(
                ExecutionDecision.FAILED,
                adjusted,
                message=f"broker_submission_failed:{type(exc).__name__}",
            )

        if not receipt.accepted:
            self._idempotency.release(request.client_order_id)
            return ExecutionResult(
                ExecutionDecision.FAILED,
                adjusted,
                order_id=receipt.order_id,
                message=receipt.message or "broker_rejected_order",
            )
        return ExecutionResult(
            ExecutionDecision.ACCEPTED,
            adjusted,
            order_id=receipt.order_id,
            message=receipt.message,
        )

    def cancel(self, order_id: str) -> bool:
        return self._broker.cancel_order(order_id)

    def replace(self, order_id: str, request: OrderRequest) -> ExecutionResult:
        if not self._idempotency.reserve(request.client_order_id):
            return ExecutionResult(
                ExecutionDecision.DUPLICATE,
                request,
                message="duplicate_client_order_id",
            )
        try:
            receipt = self._broker.replace_order(order_id, request)
        except Exception as exc:
            self._idempotency.release(request.client_order_id)
            return ExecutionResult(
                ExecutionDecision.FAILED,
                request,
                message=f"broker_replace_failed:{type(exc).__name__}",
            )
        decision = ExecutionDecision.ACCEPTED if receipt.accepted else ExecutionDecision.FAILED
        if not receipt.accepted:
            self._idempotency.release(request.client_order_id)
        return ExecutionResult(decision, request, receipt.order_id, receipt.message)

    def _block_reason(self, request: OrderRequest, context: ExecutionContext) -> str:
        if self._broker.mode is TradingMode.LIVE and not self._policy.live_enabled:
            return "live_trading_disabled"
        if not context.safety_allows_trading:
            return "production_safety_blocked"
        if self._policy.require_reconciliation and not context.reconciliation_clear:
            return "reconciliation_not_clear"
        open_orders = self._broker.list_orders(include_terminal=False)
        if len(open_orders) >= self._policy.maximum_open_orders:
            return "maximum_open_orders_reached"
        if request.quantity * context.market_price > self._policy.maximum_order_notional:
            return "maximum_order_notional_exceeded"
        return ""
