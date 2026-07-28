from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BrokerErrorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVICE_UNAVAILABLE = "service_unavailable"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    SAFETY_BLOCK = "safety_block"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BrokerErrorInfo:
    category: BrokerErrorCategory
    retryable: bool
    message: str


class BrokerError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: BrokerErrorCategory = BrokerErrorCategory.UNKNOWN,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.info = BrokerErrorInfo(category=category, retryable=retryable, message=message)


class BrokerErrorClassifier:
    """Normalizes adapter and transport failures for routing decisions."""

    @staticmethod
    def classify(exc: BaseException) -> BrokerErrorInfo:
        if isinstance(exc, BrokerError):
            return exc.info
        if isinstance(exc, TimeoutError):
            return BrokerErrorInfo(BrokerErrorCategory.TIMEOUT, True, str(exc))
        if isinstance(exc, ConnectionError):
            return BrokerErrorInfo(BrokerErrorCategory.CONNECTION, True, str(exc))
        if isinstance(exc, ValueError):
            return BrokerErrorInfo(BrokerErrorCategory.VALIDATION, False, str(exc))
        return BrokerErrorInfo(BrokerErrorCategory.UNKNOWN, False, str(exc))
