from __future__ import annotations

from dataclasses import dataclass

from src.execution.models import AccountSnapshot, OrderRequest
from src.robinhood_platform.models import RobinhoodLimits, RobinhoodReleaseStage


@dataclass(frozen=True, slots=True)
class RobinhoodOrderGateResult:
    approved: bool
    allowed_notional: float
    reasons: tuple[str, ...] = ()


class RobinhoodOrderGate:
    def __init__(self, limits: RobinhoodLimits | None = None) -> None:
        self._limits = limits or RobinhoodLimits()

    def evaluate(
        self,
        order: OrderRequest,
        *,
        reference_price: float,
        account: AccountSnapshot,
        stage: RobinhoodReleaseStage,
        open_orders: int,
        daily_submitted_notional: float,
    ) -> RobinhoodOrderGateResult:
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        reasons: list[str] = []
        if stage in {RobinhoodReleaseStage.RESEARCH, RobinhoodReleaseStage.HALTED}:
            reasons.append(f"order submission disabled in {stage.value} stage")
        if open_orders >= self._limits.max_open_orders:
            reasons.append("maximum open-order count reached")

        notional = order.quantity * reference_price
        allowed_notional = min(
            self._limits.max_order_notional,
            max(0.0, self._limits.max_daily_notional - daily_submitted_notional),
            account.equity * self._limits.max_symbol_exposure_fraction,
        )
        if stage is RobinhoodReleaseStage.CANARY:
            allowed_notional = min(
                allowed_notional,
                account.equity * self._limits.canary_capital_fraction,
            )
        if notional > allowed_notional:
            reasons.append("order notional exceeds Robinhood governance limit")
        if notional > account.buying_power:
            reasons.append("insufficient buying power")
        return RobinhoodOrderGateResult(not reasons, allowed_notional, tuple(reasons))
