from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.strategies.regime import RegimeAssessment
from src.strategies.short_swing import ShortSwingCandidate

FEATURE_NAMES = (
    "ensemble_score",
    "momentum",
    "breakout",
    "pullback",
    "quality",
    "regime_confidence",
)


@dataclass(frozen=True)
class OpportunityRankingConfig:
    minimum_training_rows: int = 40
    minimum_positive_rows: int = 8
    ml_weight: float = 0.65

    def __post_init__(self) -> None:
        if self.minimum_training_rows < 2 or self.minimum_positive_rows < 1:
            raise ValueError("training thresholds must be positive")
        if not 0 <= self.ml_weight <= 1:
            raise ValueError("ml_weight must be between zero and one")


@dataclass(frozen=True)
class OpportunityTrainingRow:
    features: Mapping[str, float]
    profitable: bool


@dataclass(frozen=True)
class RankedOpportunity:
    candidate: ShortSwingCandidate
    probability: float
    final_score: float
    source: str


class MLOpportunityRanker:
    """Rank candidates with a trained classifier and deterministic fallback."""

    def __init__(self, config: OpportunityRankingConfig | None = None) -> None:
        self.config = config or OpportunityRankingConfig()
        self._model: Pipeline | None = None

    @property
    def trained(self) -> bool:
        return self._model is not None

    def fit(self, rows: Sequence[OpportunityTrainingRow]) -> bool:
        if len(rows) < self.config.minimum_training_rows:
            self._model = None
            return False
        labels = np.asarray([int(row.profitable) for row in rows], dtype=int)
        positives = int(labels.sum())
        if positives < self.config.minimum_positive_rows or positives == len(labels):
            self._model = None
            return False
        matrix = np.asarray([self._vector(row.features) for row in rows], dtype=float)
        model = Pipeline(
            [("scale", StandardScaler()), ("classifier", LogisticRegression(max_iter=500))]
        )
        model.fit(matrix, labels)
        self._model = model
        return True

    def rank(
        self,
        candidates: Sequence[ShortSwingCandidate],
        regime: RegimeAssessment | None = None,
    ) -> tuple[RankedOpportunity, ...]:
        ranked: list[RankedOpportunity] = []
        confidence = regime.confidence if regime is not None else 0.5
        for candidate in candidates:
            features = self.features(candidate, confidence)
            fallback = self._fallback_probability(features)
            if self._model is None:
                probability = fallback
                source = "deterministic_fallback"
            else:
                ml_probability = float(
                    self._model.predict_proba(np.asarray([self._vector(features)]))[0, 1]
                )
                probability = (
                    self.config.ml_weight * ml_probability
                    + (1.0 - self.config.ml_weight) * fallback
                )
                source = "ml_blended"
            final_score = self._bounded(0.55 * candidate.score + 0.45 * probability)
            ranked.append(RankedOpportunity(candidate, probability, final_score, source))
        return tuple(sorted(ranked, key=lambda item: (-item.final_score, item.candidate.symbol)))

    @staticmethod
    def features(candidate: ShortSwingCandidate, regime_confidence: float) -> dict[str, float]:
        return {
            "ensemble_score": candidate.score,
            "momentum": candidate.strategy_scores.get("momentum", 0.5),
            "breakout": candidate.strategy_scores.get("breakout", 0.5),
            "pullback": candidate.strategy_scores.get("pullback", 0.5),
            "quality": candidate.strategy_scores.get("quality", 0.5),
            "regime_confidence": regime_confidence,
        }

    @staticmethod
    def _vector(features: Mapping[str, float]) -> list[float]:
        return [float(features.get(name, 0.5)) for name in FEATURE_NAMES]

    @classmethod
    def _fallback_probability(cls, features: Mapping[str, float]) -> float:
        probability = (
            0.35 * features["ensemble_score"]
            + 0.15 * features["momentum"]
            + 0.15 * features["breakout"]
            + 0.10 * features["pullback"]
            + 0.15 * features["quality"]
            + 0.10 * features["regime_confidence"]
        )
        return cls._bounded(probability)

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, value))
