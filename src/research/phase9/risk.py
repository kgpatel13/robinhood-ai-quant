from __future__ import annotations

from dataclasses import dataclass

from src.research.phase9.models import MarketProfile


@dataclass(frozen=True)
class PositionPlan:
    stop_price: float
    target_price: float
    quantity: float
    notional: float
    weight: float


def position_plan(
    price: float, atr: float, account_equity: float, score: float, profile: MarketProfile
) -> PositionPlan:
    if price <= 0 or atr <= 0:
        return PositionPlan(price, price, 0.0, 0.0, 0.0)
    stop_distance = max(atr * profile.stop_atr_multiple, price * 0.0025)
    target_distance = max(atr * profile.target_atr_multiple, stop_distance * 1.25)
    confidence_multiplier = min(1.25, max(0.5, score / profile.strong_entry_score))
    risk_budget = account_equity * profile.risk_per_trade * confidence_multiplier
    quantity_by_risk = risk_budget / stop_distance
    maximum_notional = account_equity * profile.maximum_position_weight
    quantity = min(quantity_by_risk, maximum_notional / price)
    notional = max(0.0, quantity * price)
    return PositionPlan(
        stop_price=round(max(0.0, price - stop_distance), 8),
        target_price=round(price + target_distance, 8),
        quantity=round(max(0.0, quantity), 8),
        notional=round(notional, 2),
        weight=round(notional / account_equity, 6),
    )
