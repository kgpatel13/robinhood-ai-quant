from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.session.models import TradingStyle


class SizingMethod(StrEnum):
    FIXED_FRACTIONAL = "fixed_fractional"
    VOLATILITY_TARGET = "volatility_target"
    BOUNDED_KELLY = "bounded_kelly"


@dataclass(frozen=True, slots=True)
class PositionSizingConfig:
    risk_per_trade: float = 0.01
    max_position_weight: float = 0.10
    volatility_target: float = 0.15
    kelly_cap: float = 0.25
    minimum_notional: float = 1.0
    fractional_shares: bool = True

    def __post_init__(self) -> None:
        for name in ("risk_per_trade", "max_position_weight", "volatility_target", "kelly_cap"):
            value = float(getattr(self, name))
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.minimum_notional < 0:
            raise ValueError("minimum_notional cannot be negative")


@dataclass(frozen=True, slots=True)
class PositionSizingRequest:
    equity: float
    price: float
    stop_distance: float
    confidence: float
    annualized_volatility: float
    portfolio_heat: float = 0.0
    drawdown: float = 0.0
    win_probability: float | None = None
    payoff_ratio: float | None = None
    style: TradingStyle = TradingStyle.SWING


@dataclass(frozen=True, slots=True)
class PositionSize:
    quantity: float
    notional: float
    risk_amount: float
    confidence_multiplier: float
    risk_multiplier: float
    method: SizingMethod
    explanation: str


class AdaptivePositionSizer:
    def __init__(self, config: PositionSizingConfig | None = None) -> None:
        self.config = config or PositionSizingConfig()

    def size(
        self,
        request: PositionSizingRequest,
        method: SizingMethod = SizingMethod.FIXED_FRACTIONAL,
    ) -> PositionSize:
        self._validate(request)
        confidence_multiplier = max(0.0, min(1.0, request.confidence))
        risk_multiplier = max(0.0, 1.0 - request.portfolio_heat - request.drawdown)
        style_multiplier = {
            TradingStyle.SCALPING: 0.50,
            TradingStyle.DAY_TRADING: 0.75,
            TradingStyle.SWING: 1.00,
            TradingStyle.POSITION: 0.80,
        }[request.style]
        base_risk = request.equity * self.config.risk_per_trade
        risk_amount = base_risk * confidence_multiplier * risk_multiplier * style_multiplier
        if method is SizingMethod.VOLATILITY_TARGET:
            volatility_multiplier = min(
                1.0, self.config.volatility_target / request.annualized_volatility
            )
            risk_amount *= volatility_multiplier
        elif method is SizingMethod.BOUNDED_KELLY:
            if request.win_probability is None or request.payoff_ratio is None:
                raise ValueError("bounded Kelly requires win_probability and payoff_ratio")
            edge = request.win_probability - (1 - request.win_probability) / request.payoff_ratio
            risk_amount *= max(0.0, min(self.config.kelly_cap, edge))
        quantity = risk_amount / request.stop_distance
        max_notional = request.equity * self.config.max_position_weight
        quantity = min(quantity, max_notional / request.price)
        if not self.config.fractional_shares:
            quantity = float(int(quantity))
        notional = quantity * request.price
        if notional < self.config.minimum_notional:
            quantity = 0.0
            notional = 0.0
            risk_amount = 0.0
        return PositionSize(
            quantity=float(quantity),
            notional=float(notional),
            risk_amount=float(min(risk_amount, quantity * request.stop_distance)),
            confidence_multiplier=float(confidence_multiplier),
            risk_multiplier=float(risk_multiplier),
            method=method,
            explanation=(
                f"{method.value} sizing produced ${notional:.2f} notional using "
                f"confidence {confidence_multiplier:.2f} and risk multiplier {risk_multiplier:.2f}"
            ),
        )

    @staticmethod
    def _validate(request: PositionSizingRequest) -> None:
        if request.equity <= 0 or request.price <= 0 or request.stop_distance <= 0:
            raise ValueError("equity, price, and stop_distance must be positive")
        if not 0 <= request.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        if request.annualized_volatility <= 0:
            raise ValueError("annualized_volatility must be positive")
        if not 0 <= request.portfolio_heat <= 1 or not 0 <= request.drawdown <= 1:
            raise ValueError("portfolio_heat and drawdown must be in [0, 1]")
