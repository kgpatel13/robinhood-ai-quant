from __future__ import annotations

from dataclasses import dataclass

from src.atlas_finalization.models import ValidationDecision, ValidationScorecard


@dataclass(frozen=True, slots=True)
class ChangeProposal:
    proposal_id: str
    strategy_id: str
    current_version: str
    candidate_version: str
    scorecard: ValidationScorecard
    rollback_version: str

    def __post_init__(self) -> None:
        values = (
            self.proposal_id,
            self.strategy_id,
            self.current_version,
            self.candidate_version,
            self.rollback_version,
        )
        if any(not value.strip() for value in values):
            raise ValueError("proposal identity fields are required")


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    approved: bool
    active_version: str
    reasons: tuple[str, ...]


class LearningGovernanceGate:
    @staticmethod
    def decide(proposal: ChangeProposal, *, human_approved: bool) -> GovernanceDecision:
        reasons: list[str] = []
        if proposal.scorecard.decision is not ValidationDecision.PROMOTE:
            reasons.append("candidate has not passed promotion validation")
        if not human_approved:
            reasons.append("human approval required")
        approved = not reasons
        active_version = proposal.candidate_version if approved else proposal.current_version
        return GovernanceDecision(approved, active_version, tuple(reasons))

    @staticmethod
    def rollback(proposal: ChangeProposal) -> GovernanceDecision:
        return GovernanceDecision(True, proposal.rollback_version, ("rollback activated",))
