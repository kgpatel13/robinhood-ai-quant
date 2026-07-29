from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class AgentRole(StrEnum):
    RESEARCH = "research"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    MARKET = "market"
    EXECUTION = "execution"
    SUPERVISOR = "supervisor"


class AgentAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class AgentContext:
    symbol: str
    features: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentOpinion:
    role: AgentRole
    action: AgentAction
    confidence: float
    rationale: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    proposed_size_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not 0.0 <= self.proposed_size_multiplier <= 1.0:
            raise ValueError("proposed_size_multiplier must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SupervisorPolicy:
    minimum_confidence: float = 0.55
    veto_roles: frozenset[AgentRole] = frozenset({AgentRole.RISK, AgentRole.EXECUTION})
    role_weights: Mapping[AgentRole, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CoordinatedDecision:
    symbol: str
    action: AgentAction
    confidence: float
    size_multiplier: float
    opinions: tuple[AgentOpinion, ...]
    explanation: tuple[str, ...]
    blocked: bool = False
