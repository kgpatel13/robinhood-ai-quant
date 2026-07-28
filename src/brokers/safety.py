from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.brokers.errors import BrokerError, BrokerErrorCategory


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class TradingSafetyPolicy:
    """Hard safety boundary for broker routing.

    Live routing remains disabled by default and requires both an explicit policy
    change and an adapter that advertises live-trading capability.
    """

    allowed_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False

    def validate(self, requested_mode: TradingMode, *, adapter_supports_live: bool) -> None:
        if requested_mode is TradingMode.PAPER:
            return
        if self.allowed_mode is not TradingMode.LIVE or not self.live_trading_enabled:
            raise BrokerError(
                "live order routing is disabled by the Atlas safety policy",
                category=BrokerErrorCategory.SAFETY_BLOCK,
            )
        if not adapter_supports_live:
            raise BrokerError(
                "the selected broker adapter does not support live trading",
                category=BrokerErrorCategory.UNSUPPORTED,
            )
