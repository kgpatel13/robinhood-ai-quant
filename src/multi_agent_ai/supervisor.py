from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .agents import DecisionAgent
from .models import (
    AgentAction,
    AgentContext,
    CoordinatedDecision,
    SupervisorPolicy,
)


class SupervisorAgent:
    def __init__(
        self,
        agents: Iterable[DecisionAgent],
        policy: SupervisorPolicy | None = None,
    ) -> None:
        self._agents = tuple(agents)
        self._policy = policy or SupervisorPolicy()

    def decide(self, context: AgentContext) -> CoordinatedDecision:
        opinions = tuple(agent.evaluate(context) for agent in self._agents)
        veto = next(
            (
                opinion
                for opinion in opinions
                if opinion.role in self._policy.veto_roles and opinion.action is AgentAction.BLOCK
            ),
            None,
        )
        if veto is not None:
            return CoordinatedDecision(
                symbol=context.symbol,
                action=AgentAction.BLOCK,
                confidence=veto.confidence,
                size_multiplier=0.0,
                opinions=opinions,
                explanation=veto.rationale,
                blocked=True,
            )

        scores: dict[AgentAction, float] = defaultdict(float)
        total_weight = 0.0
        size_multiplier = 1.0
        for opinion in opinions:
            weight = float(self._policy.role_weights.get(opinion.role, 1.0))
            scores[opinion.action] += opinion.confidence * weight
            total_weight += weight
            size_multiplier = min(size_multiplier, opinion.proposed_size_multiplier)

        directional: dict[AgentAction, float] = {
            candidate: score
            for candidate, score in scores.items()
            if candidate is not AgentAction.BLOCK
        }
        action = max(
            directional,
            key=lambda candidate: directional[candidate],
            default=AgentAction.HOLD,
        )
        confidence = directional.get(action, 0.0) / total_weight if total_weight else 0.0
        if confidence < self._policy.minimum_confidence:
            action = AgentAction.HOLD

        explanation = tuple(
            f"{opinion.role.value}: {reason}"
            for opinion in opinions
            for reason in opinion.rationale
        )
        return CoordinatedDecision(
            symbol=context.symbol,
            action=action,
            confidence=min(1.0, confidence),
            size_multiplier=max(0.0, min(1.0, size_multiplier)),
            opinions=opinions,
            explanation=explanation,
        )
