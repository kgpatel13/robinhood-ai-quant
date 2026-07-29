from __future__ import annotations

from datetime import UTC, datetime

from src.production_safety import (
    ProductionSafetyGuard,
    SafetyState,
    SafetyTelemetry,
)
from src.promotion_governance import (
    PromotionDecision,
    PromotionEvidence,
    StrategyPromotionGovernor,
)
from src.trading_orchestrator import (
    PaperTradeOrchestrator,
    TradeIntentDecision,
    TradeIntentRequest,
)


def _intent(**overrides: object) -> TradeIntentRequest:
    values: dict[str, object] = {
        "trade_id": "t-1",
        "symbol": "AAPL",
        "strategy": "momentum",
        "timestamp": datetime.now(UTC),
        "alpha_score": 0.65,
        "alpha_confidence": 1.0,
        "regime_approved": True,
        "regime_size_multiplier": 1.0,
        "market_quality_decision": "approve",
        "market_quality_multiplier": 1.0,
        "portfolio_health_action": "continue",
        "requested_notional": 10_000.0,
    }
    values.update(overrides)
    return TradeIntentRequest(**values)  # type: ignore[arg-type]


def test_orchestrator_approves_high_quality_trade() -> None:
    result = PaperTradeOrchestrator().evaluate(_intent())
    assert result.decision is TradeIntentDecision.APPROVE
    assert result.approved_notional == 10_000.0
    assert result.side == "buy"


def test_orchestrator_rejects_failed_regime_gate() -> None:
    result = PaperTradeOrchestrator().evaluate(_intent(regime_approved=False))
    assert result.decision is TradeIntentDecision.REJECT
    assert result.approved_notional == 0.0
    assert "regime_gate_rejected" in result.reasons


def test_orchestrator_reduces_notional_for_strategy_health() -> None:
    result = PaperTradeOrchestrator().evaluate(
        _intent(portfolio_health_action="reduce", alpha_confidence=0.8)
    )
    assert result.decision is TradeIntentDecision.REDUCE
    assert result.approved_notional == 4_000.0


def _evidence(**overrides: object) -> PromotionEvidence:
    values: dict[str, object] = {
        "strategy": "momentum",
        "current_stage": "research",
        "health_score": 90.0,
        "paper_trades": 50,
        "out_of_sample_sharpe": 1.4,
        "maximum_drawdown": 0.08,
        "execution_slippage_bps": 12.0,
        "regime_coverage": 3,
        "consecutive_healthy_reviews": 4,
    }
    values.update(overrides)
    return PromotionEvidence(**values)  # type: ignore[arg-type]


def test_governor_promotes_eligible_research_strategy() -> None:
    review = StrategyPromotionGovernor().review(_evidence())
    assert review.decision is PromotionDecision.PROMOTE_TO_SHADOW
    assert review.target_stage == "shadow"
    assert review.eligible


def test_governor_never_auto_promotes_to_live() -> None:
    review = StrategyPromotionGovernor().review(
        _evidence(current_stage="paper")
    )
    assert review.decision is PromotionDecision.HOLD
    assert review.target_stage == "paper"
    assert "manual_approval_required_for_live_execution" in review.reasons


def test_safety_guard_halts_on_stale_market_data() -> None:
    decision = ProductionSafetyGuard().evaluate(
        SafetyTelemetry(
            timestamp=datetime.now(UTC),
            daily_pnl=100.0,
            peak_equity=100_000.0,
            current_equity=99_000.0,
            consecutive_losses=0,
            order_rejection_rate=0.0,
            data_age_seconds=121.0,
            broker_connected=True,
        )
    )
    assert decision.state is SafetyState.HALTED
    assert not decision.allow_new_orders
    assert "market_data_stale" in decision.reasons


def test_safety_guard_throttles_after_loss_streak() -> None:
    decision = ProductionSafetyGuard().evaluate(
        SafetyTelemetry(
            timestamp=datetime.now(UTC),
            daily_pnl=-100.0,
            peak_equity=100_000.0,
            current_equity=99_500.0,
            consecutive_losses=5,
            order_rejection_rate=0.0,
            data_age_seconds=10.0,
            broker_connected=True,
        )
    )
    assert decision.state is SafetyState.THROTTLED
    assert decision.allow_new_orders
    assert decision.size_multiplier == 0.25
