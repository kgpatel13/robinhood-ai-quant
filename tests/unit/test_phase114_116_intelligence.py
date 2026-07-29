from src.decision import EnsembleDecisionEngine, EnsembleDecisionType, ModelSignal
from src.portfolio_intelligence import (
    IntelligentOrderProposalPipeline,
    PortfolioDecisionType,
    PortfolioIntelligenceEngine,
    PortfolioPosition,
    PortfolioRiskRequest,
)
from src.position_sizing import AdaptivePositionSizer, PositionSizingRequest


def test_ensemble_approves_strong_consensus() -> None:
    decision = EnsembleDecisionEngine().evaluate(
        (
            ModelSignal("logistic", 0.78),
            ModelSignal("forest", 0.74),
            ModelSignal("rules", 0.70),
        )
    )
    assert decision.decision is EnsembleDecisionType.APPROVE_LONG
    assert decision.confidence > 0


def test_ensemble_abstains_in_no_trade_band() -> None:
    decision = EnsembleDecisionEngine().evaluate((ModelSignal("a", 0.55), ModelSignal("b", 0.52)))
    assert decision.decision is EnsembleDecisionType.ABSTAIN


def test_adaptive_position_sizer_caps_weight() -> None:
    result = AdaptivePositionSizer().size(
        PositionSizingRequest(
            equity=100_000,
            price=100,
            stop_distance=2,
            confidence=1.0,
            annualized_volatility=0.20,
        )
    )
    assert result.notional == 10_000
    assert result.quantity == 100


def test_portfolio_engine_resizes_sector_concentration() -> None:
    decision = PortfolioIntelligenceEngine().evaluate(
        PortfolioRiskRequest(
            equity=100_000,
            requested_notional=20_000,
            symbol="AAPL",
            sector="technology",
            strategy="swing",
            proposed_risk_amount=1_000,
            positions=(PortfolioPosition("MSFT", 30_000, "technology", "swing"),),
        )
    )
    assert decision.decision is PortfolioDecisionType.RESIZE
    assert decision.approved_notional == 5_000
    assert decision.binding_limit == "sector_weight"


def test_pipeline_produces_paper_only_proposal() -> None:
    proposal = IntelligentOrderProposalPipeline().propose(
        symbol="AAPL",
        signals=(ModelSignal("a", 0.8), ModelSignal("b", 0.75)),
        sizing_request=PositionSizingRequest(
            equity=100_000,
            price=200,
            stop_distance=5,
            confidence=0.5,
            annualized_volatility=0.25,
        ),
        portfolio_request=PortfolioRiskRequest(
            equity=100_000,
            requested_notional=0,
            symbol="AAPL",
            sector="technology",
            strategy="swing",
            proposed_risk_amount=0,
        ),
    )
    assert proposal.approved
    assert proposal.side == "buy"
    assert proposal.notional > 0
