from __future__ import annotations

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.external_adapter import GuardedExternalBrokerAdapter


class AlpacaBrokerAdapter(GuardedExternalBrokerAdapter):
    """Alpaca paper/live adapter boundary backed by an injected transport."""

    name = "alpaca"
    capabilities = BrokerCapabilities(
        paper_trading=True,
        live_trading=True,
        order_replacement=True,
    )
