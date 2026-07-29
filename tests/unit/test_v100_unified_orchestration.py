from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.brokers.paper_adapter import PaperBrokerAdapter
from src.execution.paper import PaperBroker
from src.multi_agent_ai import (
    AgentAction,
    AgentContext,
    AgentOpinion,
    AgentRole,
    DecisionAgent,
    RiskAgent,
    SupervisorAgent,
    SupervisorPolicy,
)
from src.production_platform import (
    DeploymentPolicy,
    DeploymentStage,
    HealthStatus,
    KillSwitch,
    ProductionController,
    ServiceHealth,
)
from src.trading_orchestrator import (
    ApprovalGatedFeedbackEngine,
    AtomicCycleStateStore,
    ClosedTradeFeedback,
    CycleAuditStore,
    CycleRequest,
    CycleStatus,
    DecisionOrderTranslator,
    MarketObservation,
    OperationalMode,
    TranslationPolicy,
    UnifiedTradingOrchestrator,
)

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)


class FixedAgent(DecisionAgent):
    def __init__(
        self,
        role: AgentRole,
        action: AgentAction,
        confidence: float = 1.0,
        size: float = 1.0,
    ) -> None:
        self.role = role
        self._action = action
        self._confidence = confidence
        self._size = size

    def evaluate(self, context: AgentContext) -> AgentOpinion:
        return AgentOpinion(
            role=self.role,
            action=self._action,
            confidence=self._confidence,
            rationale=(f"{context.symbol} evaluated",),
            proposed_size_multiplier=self._size,
        )


def services() -> tuple[ServiceHealth, ...]:
    return tuple(
        ServiceHealth(name, HealthStatus.HEALTHY) for name in ("broker", "market_data", "risk")
    )


def build_orchestrator(
    tmp_path: Path,
    *,
    stage: DeploymentStage = DeploymentStage.PAPER,
    agent: DecisionAgent | None = None,
    kill_switch: KillSwitch | None = None,
) -> tuple[UnifiedTradingOrchestrator, PaperBrokerAdapter]:
    broker = PaperBrokerAdapter(
        PaperBroker(initial_cash=10_000.0, price_provider=lambda symbol: 100.0)
    )
    supervisor = SupervisorAgent(
        (agent or FixedAgent(AgentRole.STRATEGY, AgentAction.BUY),),
        SupervisorPolicy(minimum_confidence=0.5),
    )
    production = ProductionController(DeploymentPolicy(stage=stage), kill_switch)
    return (
        UnifiedTradingOrchestrator(
            supervisor=supervisor,
            production=production,
            broker=broker,
            services=services,
            audit_store=CycleAuditStore(tmp_path / "cycles.jsonl"),
            state_store=AtomicCycleStateStore(tmp_path / "state.json"),
            clock=lambda: NOW,
        ),
        broker,
    )


def request(
    *,
    mode: OperationalMode = OperationalMode.PAPER,
    observed_at: datetime = NOW,
    cycle_id: str = "cycle-1",
    notional: float = 1_000.0,
    reconciliation_clear: bool = True,
) -> CycleRequest:
    return CycleRequest(
        cycle_id=cycle_id,
        mode=mode,
        observation=MarketObservation("AAPL", 100.0, observed_at, {"risk_score": 0.1}),
        requested_notional=notional,
        strategy_id="trend-v1",
        reconciliation_clear=reconciliation_clear,
    )


def test_paper_cycle_submits_order(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path)
    result = orchestrator.run_cycle(request())
    assert result.status is CycleStatus.COMPLETED
    assert result.order_receipt is not None and result.order_receipt.accepted
    assert len(broker.list_orders()) == 1


def test_shadow_cycle_does_not_submit(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path)
    result = orchestrator.run_cycle(request(mode=OperationalMode.SHADOW))
    assert result.status is CycleStatus.COMPLETED
    assert result.order_request is not None
    assert result.order_receipt is None
    assert broker.list_orders() == ()


def test_backtest_cycle_does_not_submit(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path)
    result = orchestrator.run_cycle(request(mode=OperationalMode.BACKTEST))
    assert result.status is CycleStatus.COMPLETED
    assert broker.list_orders() == ()


def test_stale_data_is_blocked(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path)
    result = orchestrator.run_cycle(request(observed_at=NOW - timedelta(minutes=3)))
    assert result.status is CycleStatus.BLOCKED
    assert "market data is stale" in result.reasons
    assert broker.list_orders() == ()


def test_halted_mode_is_blocked(tmp_path: Path) -> None:
    orchestrator, _ = build_orchestrator(tmp_path)
    result = orchestrator.run_cycle(request(mode=OperationalMode.HALTED))
    assert result.status is CycleStatus.BLOCKED


def test_risk_agent_veto_blocks(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path, agent=RiskAgent(maximum_risk_score=0.05))
    result = orchestrator.run_cycle(request())
    assert result.status is CycleStatus.BLOCKED
    assert result.decision is not None and result.decision.blocked
    assert broker.list_orders() == ()


def test_hold_decision_skips_order(tmp_path: Path) -> None:
    orchestrator, _ = build_orchestrator(
        tmp_path, agent=FixedAgent(AgentRole.STRATEGY, AgentAction.HOLD)
    )
    result = orchestrator.run_cycle(request())
    assert result.status is CycleStatus.SKIPPED


def test_live_requires_clear_reconciliation(tmp_path: Path) -> None:
    orchestrator, _ = build_orchestrator(tmp_path, stage=DeploymentStage.PRODUCTION)
    result = orchestrator.run_cycle(request(mode=OperationalMode.LIVE, reconciliation_clear=False))
    assert result.status is CycleStatus.BLOCKED
    assert "broker reconciliation is not clear" in result.reasons


def test_live_kill_switch_blocks(tmp_path: Path) -> None:
    switch = KillSwitch()
    switch.engage("daily loss limit")
    orchestrator, _ = build_orchestrator(
        tmp_path, stage=DeploymentStage.PRODUCTION, kill_switch=switch
    )
    result = orchestrator.run_cycle(request(mode=OperationalMode.LIVE))
    assert result.status is CycleStatus.BLOCKED
    assert any("kill switch" in reason for reason in result.reasons)


def test_canary_applies_capital_fraction(tmp_path: Path) -> None:
    orchestrator, _ = build_orchestrator(tmp_path, stage=DeploymentStage.CANARY)
    result = orchestrator.run_cycle(request(mode=OperationalMode.CANARY, notional=10_000.0))
    assert result.order_request is not None
    assert result.order_request.quantity == pytest.approx(1.0)


def test_audit_and_state_are_persisted(tmp_path: Path) -> None:
    orchestrator, _ = build_orchestrator(tmp_path)
    orchestrator.run_cycle(request())
    audit = CycleAuditStore(tmp_path / "cycles.jsonl").read_all()
    state = AtomicCycleStateStore(tmp_path / "state.json").load()
    assert audit[0]["cycle_id"] == "cycle-1"
    assert state["last_status"] == "completed"


def test_duplicate_cycle_id_is_idempotent_at_paper_broker(tmp_path: Path) -> None:
    orchestrator, broker = build_orchestrator(tmp_path)
    first = orchestrator.run_cycle(request())
    second = orchestrator.run_cycle(request())
    assert first.order_receipt is not None
    assert second.order_receipt is not None
    assert first.order_receipt.order_id == second.order_receipt.order_id
    assert len(broker.list_orders()) == 1


def test_fractional_translation() -> None:
    translator = DecisionOrderTranslator()
    decision = SupervisorAgent((FixedAgent(AgentRole.STRATEGY, AgentAction.BUY, size=0.5),)).decide(
        AgentContext("AAPL")
    )
    order = translator.translate(
        decision,
        price=200.0,
        requested_notional=1_000.0,
        client_order_id="x",
    )
    assert order is not None and order.quantity == pytest.approx(2.5)


def test_whole_share_translation() -> None:
    translator = DecisionOrderTranslator(TranslationPolicy(allow_fractional=False))
    decision = SupervisorAgent((FixedAgent(AgentRole.STRATEGY, AgentAction.BUY),)).decide(
        AgentContext("AAPL")
    )
    order = translator.translate(
        decision,
        price=300.0,
        requested_notional=1_000.0,
        client_order_id="x",
    )
    assert order is not None and order.quantity == 3


def test_short_is_rejected_by_default() -> None:
    translator = DecisionOrderTranslator()
    decision = SupervisorAgent((FixedAgent(AgentRole.STRATEGY, AgentAction.SELL),)).decide(
        AgentContext("AAPL")
    )
    assert (
        translator.translate(decision, price=100.0, requested_notional=1_000.0, client_order_id="x")
        is None
    )


def test_minimum_notional_skips_order() -> None:
    translator = DecisionOrderTranslator(TranslationPolicy(minimum_notional=50.0))
    decision = SupervisorAgent((FixedAgent(AgentRole.STRATEGY, AgentAction.BUY, size=0.1),)).decide(
        AgentContext("AAPL")
    )
    assert (
        translator.translate(decision, price=100.0, requested_notional=100.0, client_order_id="x")
        is None
    )


def test_feedback_proposal_is_approval_gated() -> None:
    engine = ApprovalGatedFeedbackEngine()
    current = {"trend-v1": 0.5, "mean-v1": 0.5}
    proposal = engine.propose(current, ClosedTradeFeedback("trend-v1", 0.2, 0.0))
    assert proposal["trend-v1"] > current["trend-v1"]
    assert engine.apply(current, proposal, approved=False) == current
    assert engine.apply(current, proposal, approved=True) == proposal


def test_market_observation_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketObservation("AAPL", 100.0, datetime(2026, 1, 1))


def test_cycle_request_requires_positive_notional() -> None:
    with pytest.raises(ValueError, match="positive"):
        request(notional=0.0)


def test_translation_policy_validates_bounds() -> None:
    with pytest.raises(ValueError, match="bounds"):
        TranslationPolicy(minimum_notional=100.0, maximum_notional=10.0)
