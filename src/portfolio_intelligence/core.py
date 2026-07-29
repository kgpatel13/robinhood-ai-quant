from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PortfolioDecisionType(StrEnum):
    APPROVE = "approve"
    RESIZE = "resize"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    symbol: str
    market_value: float
    sector: str = "unknown"
    strategy: str = "unknown"


@dataclass(frozen=True, slots=True)
class PortfolioRiskConfig:
    max_symbol_weight: float = 0.15
    max_sector_weight: float = 0.35
    max_strategy_weight: float = 0.50
    max_gross_exposure: float = 0.95
    max_portfolio_heat: float = 0.08
    minimum_notional: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "max_symbol_weight",
            "max_sector_weight",
            "max_strategy_weight",
            "max_gross_exposure",
            "max_portfolio_heat",
        ):
            value = float(getattr(self, name))
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.minimum_notional < 0:
            raise ValueError("minimum_notional cannot be negative")


@dataclass(frozen=True, slots=True)
class PortfolioRiskRequest:
    equity: float
    requested_notional: float
    symbol: str
    sector: str
    strategy: str
    proposed_risk_amount: float
    positions: tuple[PortfolioPosition, ...] = ()
    open_risk_amount: float = 0.0


@dataclass(frozen=True, slots=True)
class PortfolioRiskDecision:
    decision: PortfolioDecisionType
    requested_notional: float
    approved_notional: float
    binding_limit: str
    gross_exposure: float
    portfolio_heat: float
    explanation: str


class PortfolioIntelligenceEngine:
    def __init__(self, config: PortfolioRiskConfig | None = None) -> None:
        self.config = config or PortfolioRiskConfig()

    def evaluate(self, request: PortfolioRiskRequest) -> PortfolioRiskDecision:
        if request.equity <= 0 or request.requested_notional < 0:
            raise ValueError("equity must be positive and requested_notional cannot be negative")
        gross = sum(max(0.0, position.market_value) for position in request.positions)
        symbol_value = sum(
            position.market_value
            for position in request.positions
            if position.symbol == request.symbol
        )
        sector_value = sum(
            position.market_value
            for position in request.positions
            if position.sector == request.sector
        )
        strategy_value = sum(
            position.market_value
            for position in request.positions
            if position.strategy == request.strategy
        )
        limits = {
            "symbol_weight": request.equity * self.config.max_symbol_weight - symbol_value,
            "sector_weight": request.equity * self.config.max_sector_weight - sector_value,
            "strategy_weight": request.equity * self.config.max_strategy_weight - strategy_value,
            "gross_exposure": request.equity * self.config.max_gross_exposure - gross,
        }
        risk_room = request.equity * self.config.max_portfolio_heat - request.open_risk_amount
        if request.proposed_risk_amount > 0:
            limits["portfolio_heat"] = (
                max(0.0, risk_room) / request.proposed_risk_amount * request.requested_notional
            )
        approved = max(0.0, min(request.requested_notional, *limits.values()))
        binding = min(limits, key=lambda name: limits[name])
        gross_after = (gross + approved) / request.equity
        risk_fraction = (
            request.proposed_risk_amount * approved / request.requested_notional
            if request.requested_notional > 0
            else 0.0
        )
        heat_after = (request.open_risk_amount + risk_fraction) / request.equity
        if approved < self.config.minimum_notional:
            decision = PortfolioDecisionType.REJECT
            approved = 0.0
        elif approved < request.requested_notional - 1e-9:
            decision = PortfolioDecisionType.RESIZE
        else:
            decision = PortfolioDecisionType.APPROVE
            binding = "none"
        return PortfolioRiskDecision(
            decision,
            float(request.requested_notional),
            float(approved),
            binding,
            float(gross_after),
            float(heat_after),
            (
                f"{decision.value}: approved ${approved:.2f} of ${request.requested_notional:.2f}; "
                f"binding limit={binding}"
            ),
        )
