from __future__ import annotations

import math

from src.execution_costs.models import (
    AssetClass,
    ExecutionCostEstimate,
    ExecutionCostProfile,
    ExecutionCostRequest,
    TradingHorizon,
)


class ExecutionCostSimulator:
    def estimate(
        self, request: ExecutionCostRequest, profile: ExecutionCostProfile
    ) -> ExecutionCostEstimate:
        notional = request.price * request.quantity
        participation = request.quantity / request.average_daily_volume
        fill_ratio = (
            min(1.0, profile.maximum_participation_rate / participation)
            if participation > 0
            else 1.0
        )
        executed_notional = notional * fill_ratio
        spread = executed_notional * profile.spread_bps / 20_000
        slippage_bps = profile.base_slippage_bps * (1.0 + request.volatility)
        slippage = executed_notional * slippage_bps / 10_000
        impact_bps = profile.impact_coefficient * math.sqrt(participation) * 10_000
        impact = executed_notional * impact_bps / 10_000
        latency = executed_notional * profile.latency_bps / 10_000
        commission = (
            profile.commission_per_order
            + profile.commission_per_unit * request.quantity * fill_ratio
        )
        annual_factor = request.holding_days / 365.0
        borrow = (
            executed_notional * profile.borrow_bps_annual / 10_000 * annual_factor
            if request.is_short
            else 0.0
        )
        financing = executed_notional * profile.financing_bps_annual / 10_000 * annual_factor
        total = spread + slippage + impact + latency + commission + borrow + financing
        total_bps = total / executed_notional * 10_000 if executed_notional else 0.0
        return ExecutionCostEstimate(
            notional=executed_notional,
            spread_cost=spread,
            slippage_cost=slippage,
            market_impact_cost=impact,
            latency_cost=latency,
            commission_cost=commission,
            borrow_cost=borrow,
            financing_cost=financing,
            total_cost=total,
            total_bps=total_bps,
            fill_ratio=fill_ratio,
        )


def default_profile(asset_class: AssetClass, horizon: TradingHorizon) -> ExecutionCostProfile:
    base: dict[AssetClass, tuple[float, float, float]] = {
        AssetClass.EQUITY: (2.0, 1.0, 0.015),
        AssetClass.CRYPTO: (8.0, 4.0, 0.035),
        AssetClass.FOREX: (1.5, 0.8, 0.010),
    }
    spread, slippage, impact = base[asset_class]
    multiplier = {
        TradingHorizon.SCALPING: 1.5,
        TradingHorizon.DAY: 1.0,
        TradingHorizon.SWING: 0.8,
        TradingHorizon.WEEKLY: 0.7,
    }[horizon]
    return ExecutionCostProfile(
        spread_bps=spread * multiplier,
        base_slippage_bps=slippage * multiplier,
        impact_coefficient=impact,
        latency_bps=0.5 if horizon is TradingHorizon.SCALPING else 0.1,
        financing_bps_annual=250.0 if asset_class is AssetClass.FOREX else 0.0,
        maximum_participation_rate=0.05 if horizon is TradingHorizon.SCALPING else 0.1,
    )
