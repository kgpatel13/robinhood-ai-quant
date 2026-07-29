from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import AgentAction, AgentContext, AgentOpinion, AgentRole


class DecisionAgent(ABC):
    role: AgentRole

    @abstractmethod
    def evaluate(self, context: AgentContext) -> AgentOpinion:
        raise NotImplementedError


@dataclass(slots=True)
class ThresholdAgent(DecisionAgent):
    role: AgentRole
    feature_name: str
    buy_threshold: float
    sell_threshold: float
    confidence: float = 0.7

    def evaluate(self, context: AgentContext) -> AgentOpinion:
        value = float(context.features.get(self.feature_name, 0.0))
        if value >= self.buy_threshold:
            action = AgentAction.BUY
            reason = f"{self.feature_name} above buy threshold"
        elif value <= self.sell_threshold:
            action = AgentAction.SELL
            reason = f"{self.feature_name} below sell threshold"
        else:
            action = AgentAction.HOLD
            reason = f"{self.feature_name} inside neutral range"
        return AgentOpinion(
            role=self.role,
            action=action,
            confidence=self.confidence,
            rationale=(reason,),
        )


@dataclass(slots=True)
class RiskAgent(DecisionAgent):
    role: AgentRole = AgentRole.RISK
    maximum_risk_score: float = 0.7

    def evaluate(self, context: AgentContext) -> AgentOpinion:
        risk_score = float(context.features.get("risk_score", 0.0))
        if risk_score > self.maximum_risk_score:
            return AgentOpinion(
                role=self.role,
                action=AgentAction.BLOCK,
                confidence=min(1.0, risk_score),
                rationale=("risk score exceeds configured limit",),
                constraints=("risk_veto",),
                proposed_size_multiplier=0.0,
            )
        size = max(0.0, 1.0 - risk_score)
        return AgentOpinion(
            role=self.role,
            action=AgentAction.HOLD,
            confidence=1.0 - risk_score,
            rationale=("risk within configured limit",),
            proposed_size_multiplier=size,
        )


@dataclass(slots=True)
class ExecutionAgent(DecisionAgent):
    role: AgentRole = AgentRole.EXECUTION

    def evaluate(self, context: AgentContext) -> AgentOpinion:
        tradable = context.metadata.get("tradable", "true").lower() == "true"
        liquid = context.features.get("liquidity_score", 1.0) >= 0.5
        if not tradable or not liquid:
            return AgentOpinion(
                role=self.role,
                action=AgentAction.BLOCK,
                confidence=1.0,
                rationale=("instrument is not safely executable",),
                constraints=("execution_veto",),
                proposed_size_multiplier=0.0,
            )
        return AgentOpinion(
            role=self.role,
            action=AgentAction.HOLD,
            confidence=0.8,
            rationale=("execution conditions acceptable",),
        )
