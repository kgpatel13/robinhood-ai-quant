from __future__ import annotations

from dataclasses import dataclass

from src.self_improving_ai import PolicyFeedback, SafeguardedPolicyUpdater


@dataclass(frozen=True, slots=True)
class ClosedTradeFeedback:
    strategy_id: str
    realized_return: float
    maximum_adverse_excursion: float


class ApprovalGatedFeedbackEngine:
    def __init__(self, updater: SafeguardedPolicyUpdater | None = None) -> None:
        self._updater = updater or SafeguardedPolicyUpdater()

    def propose(
        self,
        weights: dict[str, float],
        feedback: ClosedTradeFeedback,
    ) -> dict[str, float]:
        return self._updater.update(
            weights,
            (
                PolicyFeedback(
                    action=feedback.strategy_id,
                    reward=feedback.realized_return,
                    risk_penalty=max(0.0, feedback.maximum_adverse_excursion),
                ),
            ),
        )

    @staticmethod
    def apply(
        current: dict[str, float], proposal: dict[str, float], *, approved: bool
    ) -> dict[str, float]:
        return dict(proposal if approved else current)
