from __future__ import annotations

from src.capital_allocator.models import (
    AllocationPolicy,
    CapitalAllocationRequest,
    CapitalAllocationResult,
    SizingMethod,
)


class DynamicCapitalAllocator:
    """Converts strategy evidence into a bounded portfolio capital allocation."""

    def allocate(
        self,
        request: CapitalAllocationRequest,
        policy: AllocationPolicy | None = None,
    ) -> CapitalAllocationResult:
        selected = policy or AllocationPolicy()
        self._validate(request, selected)
        reasons: list[str] = []
        if request.current_drawdown >= selected.maximum_drawdown:
            return CapitalAllocationResult(
                request.strategy,
                0.0,
                0.0,
                0.0,
                selected.method,
                ("maximum_drawdown_reached",),
            )

        raw = self._raw_fraction(request, selected)
        confidence_adjusted = raw * request.confidence
        drawdown_multiplier = max(
            0.0,
            1.0 - request.current_drawdown / selected.maximum_drawdown,
        )
        if drawdown_multiplier < 1.0:
            reasons.append("drawdown_reduction_applied")
        allocation = confidence_adjusted * drawdown_multiplier
        if allocation > selected.maximum_allocation:
            reasons.append("maximum_allocation_applied")
        allocation = min(selected.maximum_allocation, max(0.0, allocation))
        risk_budget = min(selected.daily_risk_budget, allocation)
        return CapitalAllocationResult(
            strategy=request.strategy,
            allocation_fraction=allocation,
            allocated_capital=request.portfolio_equity * allocation,
            risk_budget=request.portfolio_equity * risk_budget,
            sizing_method=selected.method,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _raw_fraction(
        request: CapitalAllocationRequest,
        policy: AllocationPolicy,
    ) -> float:
        if policy.method is SizingMethod.FIXED_FRACTIONAL:
            return policy.fixed_fraction
        if policy.method is SizingMethod.VOLATILITY_TARGET:
            return min(1.0, policy.target_volatility / request.realized_volatility)
        win = request.expected_win_probability
        loss = 1.0 - win
        full_kelly = win - loss / request.payoff_ratio
        return max(0.0, full_kelly) * policy.kelly_fraction

    @staticmethod
    def _validate(
        request: CapitalAllocationRequest,
        policy: AllocationPolicy,
    ) -> None:
        if request.portfolio_equity <= 0:
            raise ValueError("portfolio_equity must be positive")
        if not 0.0 <= request.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not 0.0 <= request.expected_win_probability <= 1.0:
            raise ValueError("expected_win_probability must be in [0, 1]")
        if request.payoff_ratio <= 0 or request.realized_volatility <= 0:
            raise ValueError("payoff_ratio and realized_volatility must be positive")
        if not 0.0 <= request.current_drawdown <= 1.0:
            raise ValueError("current_drawdown must be in [0, 1]")
        if not 0.0 < policy.maximum_drawdown <= 1.0:
            raise ValueError("maximum_drawdown must be in (0, 1]")
