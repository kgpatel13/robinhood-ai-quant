from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    quantity: float
    side: OrderSide


@dataclass(frozen=True)
class OrderReceipt:
    order_id: str
    accepted: bool
    message: str = ""


class Broker(Protocol):
    name: str

    def submit_order(self, order: OrderRequest) -> OrderReceipt: ...

    def cancel_order(self, order_id: str) -> bool: ...
