from src.multi_agent_ai import (
    AgentAction,
    AgentContext,
    AgentRole,
    ExecutionAgent,
    RiskAgent,
    SupervisorAgent,
    SupervisorPolicy,
    ThresholdAgent,
)


def test_threshold_agent_buys() -> None:
    agent = ThresholdAgent(AgentRole.STRATEGY, "momentum", 0.5, -0.5)
    opinion = agent.evaluate(AgentContext("AAPL", {"momentum": 0.8}))
    assert opinion.action is AgentAction.BUY


def test_threshold_agent_sells() -> None:
    agent = ThresholdAgent(AgentRole.MARKET, "trend", 0.5, -0.5)
    opinion = agent.evaluate(AgentContext("AAPL", {"trend": -0.8}))
    assert opinion.action is AgentAction.SELL


def test_threshold_agent_holds() -> None:
    agent = ThresholdAgent(AgentRole.RESEARCH, "alpha", 0.5, -0.5)
    opinion = agent.evaluate(AgentContext("AAPL", {"alpha": 0.1}))
    assert opinion.action is AgentAction.HOLD


def test_risk_agent_vetoes() -> None:
    opinion = RiskAgent(maximum_risk_score=0.6).evaluate(AgentContext("AAPL", {"risk_score": 0.9}))
    assert opinion.action is AgentAction.BLOCK
    assert opinion.proposed_size_multiplier == 0.0


def test_execution_agent_vetoes_untradable_symbol() -> None:
    opinion = ExecutionAgent().evaluate(AgentContext("AAPL", metadata={"tradable": "false"}))
    assert opinion.action is AgentAction.BLOCK


def test_supervisor_honors_veto() -> None:
    supervisor = SupervisorAgent(
        [
            ThresholdAgent(AgentRole.STRATEGY, "momentum", 0.5, -0.5, 0.9),
            RiskAgent(maximum_risk_score=0.6),
        ]
    )
    decision = supervisor.decide(AgentContext("AAPL", {"momentum": 1.0, "risk_score": 0.8}))
    assert decision.blocked
    assert decision.action is AgentAction.BLOCK


def test_supervisor_combines_votes_and_size() -> None:
    supervisor = SupervisorAgent(
        [
            ThresholdAgent(AgentRole.STRATEGY, "momentum", 0.5, -0.5, 0.9),
            ThresholdAgent(AgentRole.MARKET, "trend", 0.5, -0.5, 0.8),
            RiskAgent(maximum_risk_score=0.9),
        ],
        SupervisorPolicy(minimum_confidence=0.5),
    )
    context = AgentContext("AAPL", {"momentum": 1.0, "trend": 1.0, "risk_score": 0.2})
    decision = supervisor.decide(context)
    assert decision.action is AgentAction.BUY
    assert decision.size_multiplier == 0.8
    assert decision.explanation


def test_supervisor_falls_back_to_hold_when_confidence_is_low() -> None:
    supervisor = SupervisorAgent(
        [ThresholdAgent(AgentRole.STRATEGY, "momentum", 0.5, -0.5, 0.3)],
        SupervisorPolicy(minimum_confidence=0.8),
    )
    decision = supervisor.decide(AgentContext("AAPL", {"momentum": 1.0}))
    assert decision.action is AgentAction.HOLD
