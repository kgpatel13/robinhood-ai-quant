from __future__ import annotations

from src.atlas_v18.models import PositionSize, PositionSizingInput


class DynamicPositionSizer:
    def __init__(
        self,
        *,
        base_risk_pct: float = 0.005,
        max_position_pct: float = 0.05,
        max_total_exposure_pct: float = 0.50,
        target_volatility: float = 0.20,
    ) -> None:
        if min(base_risk_pct, max_position_pct, max_total_exposure_pct, target_volatility) <= 0:
            raise ValueError("position sizing limits must be positive")
        self.base_risk_pct = base_risk_pct
        self.max_position_pct = max_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.target_volatility = target_volatility

    def size(self, values: PositionSizingInput) -> PositionSize:
        if values.equity <= 0 or values.price <= 0:
            raise ValueError("equity and price must be positive")
        confidence = min(1.0, max(0.0, values.confidence))
        volatility = max(values.annualized_volatility, 0.01)
        volatility_scale = min(1.5, self.target_volatility / volatility)
        drawdown_scale = max(0.10, 1.0 - max(0.0, values.current_drawdown) * 4.0)
        risk_budget_pct = self.base_risk_pct * confidence * volatility_scale * drawdown_scale
        raw_pct = min(self.max_position_pct, risk_budget_pct / max(volatility, 0.01))
        exposure_capacity = max(0.0, self.max_total_exposure_pct - values.current_exposure_pct)
        portfolio_pct = min(raw_pct, exposure_capacity)
        caps: list[str] = []
        if raw_pct >= self.max_position_pct - 1e-12:
            caps.append("max_position_pct")
        if exposure_capacity <= raw_pct + 1e-12:
            caps.append("max_total_exposure_pct")
        notional = values.equity * portfolio_pct
        return PositionSize(
            quantity=notional / values.price,
            notional=notional,
            portfolio_pct=portfolio_pct,
            risk_budget_pct=risk_budget_pct,
            capped_by=tuple(caps),
        )
