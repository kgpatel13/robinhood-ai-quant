from __future__ import annotations

from src.brokers.capabilities import BrokerCapabilities
from src.brokers.external_adapter import GuardedExternalBrokerAdapter


class RobinhoodBrokerAdapter(GuardedExternalBrokerAdapter):
    """Safe Robinhood integration boundary.

    A concrete transport must be supplied. Atlas does not embed credentials or
    depend on unofficial login automation in this adapter.
    """

    name = "robinhood"
    capabilities = BrokerCapabilities(
        paper_trading=False,
        live_trading=True,
        order_replacement=False,
    )
