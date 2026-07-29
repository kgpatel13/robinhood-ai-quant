from __future__ import annotations

from dataclasses import dataclass

from src.decision import EnsembleDecision, EnsembleDecisionEngine, EnsembleDecisionType, ModelSignal
from src.portfolio_intelligence.core import (
    PortfolioDecisionType,
    PortfolioIntelligenceEngine,
    PortfolioRiskDecision,
    PortfolioRiskRequest,
)
from src.position_sizing import AdaptivePositionSizer, PositionSize, PositionSizingRequest


@dataclass(frozen=True, slots=True)
class PaperOrderProposal:
    symbol: str
    side: str
    quantity: float
    notional: float
    approved: bool
    ensemble: EnsembleDecision
    sizing: PositionSize | None
    portfolio: PortfolioRiskDecision | None


class IntelligentOrderProposalPipeline:
    """Produces paper-only proposals; it never sends an order to a broker."""

    def __init__(
        self,
        ensemble: EnsembleDecisionEngine | None = None,
        sizer: AdaptivePositionSizer | None = None,
        portfolio: PortfolioIntelligenceEngine | None = None,
    ) -> None:
        self.ensemble = ensemble or EnsembleDecisionEngine()
        self.sizer = sizer or AdaptivePositionSizer()
        self.portfolio = portfolio or PortfolioIntelligenceEngine()

    def propose(
        self,
        *,
        symbol: str,
        signals: tuple[ModelSignal, ...],
        sizing_request: PositionSizingRequest,
        portfolio_request: PortfolioRiskRequest,
    ) -> PaperOrderProposal:
        ensemble = self.ensemble.evaluate(signals)
        if ensemble.decision is EnsembleDecisionType.ABSTAIN:
            return PaperOrderProposal(symbol, "none", 0.0, 0.0, False, ensemble, None, None)
        sizing_request = PositionSizingRequest(
            equity=sizing_request.equity,
            price=sizing_request.price,
            stop_distance=sizing_request.stop_distance,
            confidence=ensemble.confidence,
            annualized_volatility=sizing_request.annualized_volatility,
            portfolio_heat=sizing_request.portfolio_heat,
            drawdown=sizing_request.drawdown,
            win_probability=sizing_request.win_probability,
            payoff_ratio=sizing_request.payoff_ratio,
            style=sizing_request.style,
        )
        sizing = self.sizer.size(sizing_request)
        adjusted = PortfolioRiskRequest(
            equity=portfolio_request.equity,
            requested_notional=sizing.notional,
            symbol=portfolio_request.symbol,
            sector=portfolio_request.sector,
            strategy=portfolio_request.strategy,
            proposed_risk_amount=sizing.risk_amount,
            positions=portfolio_request.positions,
            open_risk_amount=portfolio_request.open_risk_amount,
        )
        portfolio = self.portfolio.evaluate(adjusted)
        approved = portfolio.decision is not PortfolioDecisionType.REJECT
        quantity = portfolio.approved_notional / sizing_request.price if approved else 0.0
        side = "buy" if ensemble.decision is EnsembleDecisionType.APPROVE_LONG else "sell"
        return PaperOrderProposal(
            symbol,
            side,
            float(quantity),
            float(portfolio.approved_notional),
            approved,
            ensemble,
            sizing,
            portfolio,
        )
