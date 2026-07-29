from __future__ import annotations

import math

from src.execution.models import OrderRequest, OrderSide
from src.multi_agent_ai.models import AgentAction, CoordinatedDecision

from .integration_models import TranslationPolicy


class DecisionOrderTranslator:
    def __init__(self, policy: TranslationPolicy | None = None) -> None:
        self._policy = policy or TranslationPolicy()

    def translate(
        self,
        decision: CoordinatedDecision,
        *,
        price: float,
        requested_notional: float,
        capital_fraction: float = 1.0,
        client_order_id: str,
    ) -> OrderRequest | None:
        if price <= 0:
            raise ValueError("price must be positive")
        if decision.blocked or decision.action in {AgentAction.BLOCK, AgentAction.HOLD}:
            return None
        if decision.action in {AgentAction.EXIT, AgentAction.REDUCE}:
            return None

        side = OrderSide.BUY if decision.action is AgentAction.BUY else OrderSide.SELL
        if side is OrderSide.SELL and not self._policy.allow_short:
            return None

        notional = requested_notional * decision.size_multiplier * capital_fraction
        notional = min(notional, self._policy.maximum_notional)
        if notional < self._policy.minimum_notional:
            return None

        quantity = notional / price
        if not self._policy.allow_fractional:
            quantity = math.floor(quantity)
        if quantity <= 0:
            return None
        return OrderRequest(
            symbol=decision.symbol,
            quantity=quantity,
            side=side,
            client_order_id=client_order_id,
        )
