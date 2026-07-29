from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SignalDirection(StrEnum):
    SHORT = "short"
    FLAT = "flat"
    LONG = "long"


class EnsembleDecisionType(StrEnum):
    APPROVE_LONG = "approve_long"
    APPROVE_SHORT = "approve_short"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class ModelSignal:
    source: str
    probability_long: float
    weight: float = 1.0
    reliability: float = 1.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not 0 <= self.probability_long <= 1:
            raise ValueError("probability_long must be in [0, 1]")
        if self.weight <= 0:
            raise ValueError("weight must be positive")
        if not 0 <= self.reliability <= 1:
            raise ValueError("reliability must be in [0, 1]")

    @property
    def effective_weight(self) -> float:
        return self.weight * self.reliability


@dataclass(frozen=True, slots=True)
class EnsembleConfig:
    long_threshold: float = 0.60
    short_threshold: float = 0.40
    minimum_agreement: float = 0.60
    maximum_disagreement: float = 0.18
    minimum_sources: int = 2

    def __post_init__(self) -> None:
        if not 0 <= self.short_threshold < self.long_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 <= short < long <= 1")
        if not 0 <= self.minimum_agreement <= 1:
            raise ValueError("minimum_agreement must be in [0, 1]")
        if self.maximum_disagreement < 0:
            raise ValueError("maximum_disagreement cannot be negative")
        if self.minimum_sources < 1:
            raise ValueError("minimum_sources must be positive")


@dataclass(frozen=True, slots=True)
class EnsembleDecision:
    decision: EnsembleDecisionType
    direction: SignalDirection
    probability_long: float
    confidence: float
    agreement: float
    disagreement: float
    contributors: tuple[str, ...]
    explanation: str


class EnsembleDecisionEngine:
    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig()

    def evaluate(self, signals: tuple[ModelSignal, ...]) -> EnsembleDecision:
        if len(signals) < self.config.minimum_sources:
            return self._abstain(signals, "insufficient ensemble sources")
        total_weight = sum(signal.effective_weight for signal in signals)
        if total_weight <= 0:
            return self._abstain(signals, "zero effective ensemble weight")
        probability = (
            sum(signal.probability_long * signal.effective_weight for signal in signals)
            / total_weight
        )
        disagreement = (
            sum(
                signal.effective_weight * abs(signal.probability_long - probability)
                for signal in signals
            )
            / total_weight
        )
        if probability >= self.config.long_threshold:
            direction = SignalDirection.LONG
            decision = EnsembleDecisionType.APPROVE_LONG
            agreeing = sum(
                signal.effective_weight
                for signal in signals
                if signal.probability_long >= self.config.long_threshold
            )
        elif probability <= self.config.short_threshold:
            direction = SignalDirection.SHORT
            decision = EnsembleDecisionType.APPROVE_SHORT
            agreeing = sum(
                signal.effective_weight
                for signal in signals
                if signal.probability_long <= self.config.short_threshold
            )
        else:
            return self._abstain(signals, "consensus probability is inside the no-trade band")
        agreement = agreeing / total_weight
        confidence = min(1.0, abs(probability - 0.5) * 2.0 * agreement)
        if agreement < self.config.minimum_agreement:
            return self._abstain(signals, "minimum agreement was not reached")
        if disagreement > self.config.maximum_disagreement:
            return self._abstain(signals, "model disagreement exceeded the configured limit")
        return EnsembleDecision(
            decision=decision,
            direction=direction,
            probability_long=float(probability),
            confidence=float(confidence),
            agreement=float(agreement),
            disagreement=float(disagreement),
            contributors=tuple(signal.source for signal in signals),
            explanation=(
                f"{direction.value} consensus approved with probability {probability:.3f}, "
                f"agreement {agreement:.3f}, and disagreement {disagreement:.3f}"
            ),
        )

    def _abstain(self, signals: tuple[ModelSignal, ...], reason: str) -> EnsembleDecision:
        probability = (
            sum(signal.probability_long for signal in signals) / len(signals) if signals else 0.5
        )
        return EnsembleDecision(
            EnsembleDecisionType.ABSTAIN,
            SignalDirection.FLAT,
            float(probability),
            0.0,
            0.0,
            0.0,
            tuple(signal.source for signal in signals),
            reason,
        )
