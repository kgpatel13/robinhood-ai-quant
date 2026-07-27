from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from src.execution.broker import Broker
from src.execution.models import OrderReceipt, OrderRequest


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0 or self.backoff_multiplier < 1:
            raise ValueError("invalid retry policy")


class OrderRouter:
    def __init__(self, broker: Broker, *, retry_policy: RetryPolicy | None = None) -> None:
        self._broker = broker
        self._retry = retry_policy or RetryPolicy()
        self._receipts: dict[str, OrderReceipt] = {}

    def submit(self, order: OrderRequest) -> OrderReceipt:
        cached = self._receipts.get(order.client_order_id)
        if cached is not None:
            return cached
        delay = self._retry.initial_delay_seconds
        last_error = "order submission failed"
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                receipt = self._broker.submit_order(order)
                self._receipts[order.client_order_id] = receipt
                return receipt
            except (ConnectionError, TimeoutError) as exc:
                last_error = str(exc)
                if attempt < self._retry.max_attempts and delay > 0:
                    sleep(delay)
                    delay *= self._retry.backoff_multiplier
        return OrderReceipt("", False, last_error, order.client_order_id)

    def cancel_replace(self, order_id: str, replacement: OrderRequest) -> OrderReceipt:
        if not self._broker.cancel_order(order_id):
            return OrderReceipt(order_id, False, "original order could not be cancelled")
        return self.submit(replacement)
