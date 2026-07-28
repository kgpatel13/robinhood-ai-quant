from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from src.brokers.audit import BrokerAuditLog
from src.brokers.base import BrokerAdapter
from src.brokers.errors import BrokerErrorClassifier
from src.execution.models import OrderReceipt, OrderRequest


@dataclass(frozen=True)
class BrokerRetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds cannot be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")


class BrokerOrderRouter:
    """Idempotent adapter router with classified retry behavior."""

    def __init__(
        self,
        adapter: BrokerAdapter,
        *,
        retry_policy: BrokerRetryPolicy | None = None,
        audit_log: BrokerAuditLog | None = None,
    ) -> None:
        self._adapter = adapter
        self._retry = retry_policy or BrokerRetryPolicy()
        self._audit = audit_log
        self._receipts: dict[str, OrderReceipt] = {}

    def submit(self, order: OrderRequest) -> OrderReceipt:
        cached = self._receipts.get(order.client_order_id)
        if cached is not None:
            return cached

        delay = self._retry.initial_delay_seconds
        last_message = "order submission failed"
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                receipt = self._adapter.submit_order(order)
                self._receipts[order.client_order_id] = receipt
                return receipt
            except Exception as exc:
                info = BrokerErrorClassifier.classify(exc)
                last_message = info.message
                self._record_failure(order, attempt, info.category.value, info.retryable)
                if not info.retryable or attempt >= self._retry.max_attempts:
                    break
                if delay > 0:
                    sleep(delay)
                    delay *= self._retry.backoff_multiplier

        receipt = OrderReceipt("", False, last_message, order.client_order_id)
        self._receipts[order.client_order_id] = receipt
        return receipt

    def _record_failure(
        self,
        order: OrderRequest,
        attempt: int,
        category: str,
        retryable: bool,
    ) -> None:
        if self._audit is not None:
            self._audit.append(
                event_type="order_submission_failed",
                broker=self._adapter.name,
                entity_id=order.client_order_id,
                payload={"attempt": attempt, "category": category, "retryable": retryable},
            )
