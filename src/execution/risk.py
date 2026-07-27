from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from src.execution.models import AccountSnapshot, OrderRequest, OrderSide


class RiskDecisionType(StrEnum):
    APPROVE = "approve"
    RESIZE = "resize"
    REJECT = "reject"


class RiskReason(StrEnum):
    APPROVED = "approved"
    INVALID_PRICE = "invalid_price"
    INVALID_QUANTITY = "invalid_quantity"
    ORDER_NOTIONAL_LIMIT = "order_notional_limit"
    POSITION_WEIGHT_LIMIT = "position_weight_limit"
    GROSS_EXPOSURE_LIMIT = "gross_exposure_limit"
    CASH_RESERVE_LIMIT = "cash_reserve_limit"
    OPEN_POSITION_LIMIT = "open_position_limit"
    INSUFFICIENT_POSITION = "insufficient_position"
    BELOW_MIN_NOTIONAL = "below_min_notional"


@dataclass(frozen=True)
class PreTradeRiskConfig:
    max_position_weight: float = 0.25
    max_order_notional: float = 2_500.0
    max_gross_exposure: float = 0.95
    min_cash_reserve: float = 0.05
    max_open_positions: int = 10
    min_order_notional: float = 1.0

    def __post_init__(self) -> None:
        for name in ("max_position_weight", "max_gross_exposure", "min_cash_reserve"):
            value = float(getattr(self, name))
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.max_position_weight > self.max_gross_exposure:
            raise ValueError("max_position_weight cannot exceed max_gross_exposure")
        if self.max_gross_exposure + self.min_cash_reserve > 1 + 1e-9:
            raise ValueError("gross exposure and cash reserve limits are inconsistent")
        if self.max_order_notional <= 0 or self.min_order_notional < 0:
            raise ValueError("invalid order notional limits")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be positive")


@dataclass(frozen=True)
class RiskDecision:
    decision: RiskDecisionType
    reason: RiskReason
    original_order: OrderRequest
    approved_order: OrderRequest | None
    original_notional: float
    approved_notional: float
    details: str = ""


@dataclass(frozen=True)
class RiskEvaluation:
    decisions: tuple[RiskDecision, ...]

    @property
    def approved_orders(self) -> tuple[OrderRequest, ...]:
        approved: list[OrderRequest] = []
        for decision in self.decisions:
            if decision.approved_order is not None:
                approved.append(decision.approved_order)
        return tuple(approved)

    @property
    def approved_count(self) -> int:
        return sum(decision.decision is RiskDecisionType.APPROVE for decision in self.decisions)

    @property
    def resized_count(self) -> int:
        return sum(decision.decision is RiskDecisionType.RESIZE for decision in self.decisions)

    @property
    def rejected_count(self) -> int:
        return sum(decision.decision is RiskDecisionType.REJECT for decision in self.decisions)


class PreTradeRiskEngine:
    """Deterministic pre-trade controls for long-only paper orders."""

    def __init__(self, config: PreTradeRiskConfig | None = None) -> None:
        self.config = config or PreTradeRiskConfig()

    def evaluate(
        self,
        orders: tuple[OrderRequest, ...],
        account: AccountSnapshot,
        prices: dict[str, float],
    ) -> RiskEvaluation:
        positions = {position.symbol: position.quantity for position in account.positions}
        values = {position.symbol: position.market_value for position in account.positions}
        cash = account.cash
        decisions: list[RiskDecision] = []

        for order in orders:
            price = prices.get(order.symbol, 0.0)
            decision = self._evaluate_one(order, price, account.equity, cash, positions, values)
            decisions.append(decision)
            approved = decision.approved_order
            if approved is None:
                continue
            notional = approved.quantity * price
            if approved.side is OrderSide.BUY:
                cash -= notional
                positions[approved.symbol] = positions.get(approved.symbol, 0.0) + approved.quantity
                values[approved.symbol] = values.get(approved.symbol, 0.0) + notional
            else:
                cash += notional
                positions[approved.symbol] = max(
                    0.0, positions.get(approved.symbol, 0.0) - approved.quantity
                )
                values[approved.symbol] = max(0.0, values.get(approved.symbol, 0.0) - notional)
        return RiskEvaluation(tuple(decisions))

    def _evaluate_one(
        self,
        order: OrderRequest,
        price: float,
        equity: float,
        cash: float,
        positions: dict[str, float],
        values: dict[str, float],
    ) -> RiskDecision:
        if price <= 0:
            return self._reject(order, 0.0, RiskReason.INVALID_PRICE)
        notional = order.quantity * price
        if order.quantity <= 0:
            return self._reject(order, notional, RiskReason.INVALID_QUANTITY)
        if notional < self.config.min_order_notional:
            return self._reject(order, notional, RiskReason.BELOW_MIN_NOTIONAL)

        if order.side is OrderSide.SELL:
            available = positions.get(order.symbol, 0.0)
            if available <= 0:
                return self._reject(order, notional, RiskReason.INSUFFICIENT_POSITION)
            quantity = min(order.quantity, available)
            return self._finalize(order, quantity, price, RiskReason.INSUFFICIENT_POSITION)

        existing_value = values.get(order.symbol, 0.0)
        open_symbols = {symbol for symbol, value in values.items() if value > 1e-9}
        if order.symbol not in open_symbols and len(open_symbols) >= self.config.max_open_positions:
            return self._reject(order, notional, RiskReason.OPEN_POSITION_LIMIT)

        max_position_add = max(0.0, equity * self.config.max_position_weight - existing_value)
        gross_value = sum(max(0.0, value) for value in values.values())
        max_gross_add = max(0.0, equity * self.config.max_gross_exposure - gross_value)
        max_cash_spend = max(0.0, cash - equity * self.config.min_cash_reserve)
        allowed = min(
            notional,
            self.config.max_order_notional,
            max_position_add,
            max_gross_add,
            max_cash_spend,
        )
        if allowed < self.config.min_order_notional:
            reason = self._binding_reason(notional, max_position_add, max_gross_add, max_cash_spend)
            return self._reject(order, notional, reason)
        reason = self._binding_reason(notional, max_position_add, max_gross_add, max_cash_spend)
        return self._finalize(order, allowed / price, price, reason)

    def _binding_reason(
        self,
        requested: float,
        max_position_add: float,
        max_gross_add: float,
        max_cash_spend: float,
    ) -> RiskReason:
        limits = {
            RiskReason.ORDER_NOTIONAL_LIMIT: self.config.max_order_notional,
            RiskReason.POSITION_WEIGHT_LIMIT: max_position_add,
            RiskReason.GROSS_EXPOSURE_LIMIT: max_gross_add,
            RiskReason.CASH_RESERVE_LIMIT: max_cash_spend,
        }
        reason, amount = min(limits.items(), key=lambda item: item[1])
        return RiskReason.APPROVED if requested <= amount + 1e-9 else reason

    @staticmethod
    def _reject(order: OrderRequest, notional: float, reason: RiskReason) -> RiskDecision:
        return RiskDecision(
            RiskDecisionType.REJECT,
            reason,
            order,
            None,
            notional,
            0.0,
        )

    @staticmethod
    def _finalize(
        order: OrderRequest,
        quantity: float,
        price: float,
        reason: RiskReason,
    ) -> RiskDecision:
        approved = replace(order, quantity=quantity)
        original_notional = order.quantity * price
        approved_notional = quantity * price
        resized = quantity < order.quantity - 1e-9
        return RiskDecision(
            RiskDecisionType.RESIZE if resized else RiskDecisionType.APPROVE,
            reason if resized else RiskReason.APPROVED,
            order,
            approved,
            original_notional,
            approved_notional,
        )
