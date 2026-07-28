from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerCapabilities:
    """Declarative feature flags exposed by a broker adapter."""

    paper_trading: bool
    live_trading: bool = False
    market_orders: bool = True
    limit_orders: bool = True
    fractional_shares: bool = True
    order_cancellation: bool = True
    order_replacement: bool = False
    positions: bool = True
    account_snapshot: bool = True
    fills: bool = True

    def require(self, capability: str) -> None:
        if not hasattr(self, capability):
            raise ValueError(f"unknown broker capability: {capability}")
        if not bool(getattr(self, capability)):
            raise RuntimeError(f"broker capability is unavailable: {capability}")
