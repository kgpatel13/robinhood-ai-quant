from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StrategyGrade(StrEnum):
    INSTITUTION_GRADE = "institution_grade"
    PRODUCTION_CANDIDATE = "production_candidate"
    RESEARCH_ONLY = "research_only"
    REJECTED = "rejected"


@dataclass(frozen=True)
class StrategyMetrics:
    annual_return: float
    sharpe_ratio: float
    maximum_drawdown: float
    consistency: float
    regime_stability: float
    turnover: float
    execution_cost_bps: float
    prediction_quality: float
    out_of_sample_return: float


@dataclass(frozen=True)
class StrategyScore:
    name: str
    score: float
    grade: StrategyGrade
    components: dict[str, float]
    rejection_reasons: tuple[str, ...]
    deploy_to_paper: bool


@dataclass(frozen=True)
class StrategyRankingPolicy:
    minimum_out_of_sample_return: float = 0.0
    maximum_drawdown: float = 0.35
    minimum_sharpe: float = 0.5
    maximum_execution_cost_bps: float = 75.0


class StrategyRanker:
    def __init__(self, policy: StrategyRankingPolicy | None = None) -> None:
        self.policy = policy or StrategyRankingPolicy()

    def score(self, name: str, metrics: StrategyMetrics) -> StrategyScore:
        reasons = self._rejection_reasons(metrics)
        components = {
            "profitability": self._clamp(metrics.annual_return / 0.30) * 22,
            "sharpe": self._clamp(metrics.sharpe_ratio / 2.0) * 18,
            "drawdown": self._clamp(
                1.0 - metrics.maximum_drawdown / self.policy.maximum_drawdown
            )
            * 18,
            "consistency": self._clamp(metrics.consistency) * 15,
            "regime_stability": self._clamp(metrics.regime_stability) * 10,
            "turnover": self._clamp(1.0 - metrics.turnover / 10.0) * 5,
            "execution_cost": self._clamp(
                1.0
                - metrics.execution_cost_bps / self.policy.maximum_execution_cost_bps
            )
            * 7,
            "prediction_quality": self._clamp(metrics.prediction_quality) * 5,
        }
        raw_score = sum(components.values())
        score = 0.0 if reasons else raw_score
        grade = self._grade(score, bool(reasons))
        return StrategyScore(
            name=name,
            score=round(score, 4),
            grade=grade,
            components={key: round(value, 4) for key, value in components.items()},
            rejection_reasons=reasons,
            deploy_to_paper=grade
            in {StrategyGrade.INSTITUTION_GRADE, StrategyGrade.PRODUCTION_CANDIDATE},
        )

    def rank(self, strategies: dict[str, StrategyMetrics]) -> tuple[StrategyScore, ...]:
        scores = (self.score(name, metrics) for name, metrics in strategies.items())
        return tuple(sorted(scores, key=lambda item: item.score, reverse=True))

    def _rejection_reasons(self, metrics: StrategyMetrics) -> tuple[str, ...]:
        reasons: list[str] = []
        if metrics.out_of_sample_return <= self.policy.minimum_out_of_sample_return:
            reasons.append("non-positive out-of-sample return")
        if metrics.maximum_drawdown > self.policy.maximum_drawdown:
            reasons.append("maximum drawdown exceeds policy")
        if metrics.sharpe_ratio < self.policy.minimum_sharpe:
            reasons.append("Sharpe ratio below policy")
        if metrics.execution_cost_bps > self.policy.maximum_execution_cost_bps:
            reasons.append("execution cost exceeds policy")
        return tuple(reasons)

    @staticmethod
    def _grade(score: float, rejected: bool) -> StrategyGrade:
        if rejected:
            return StrategyGrade.REJECTED
        if score >= 80:
            return StrategyGrade.INSTITUTION_GRADE
        if score >= 65:
            return StrategyGrade.PRODUCTION_CANDIDATE
        return StrategyGrade.RESEARCH_ONLY

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
