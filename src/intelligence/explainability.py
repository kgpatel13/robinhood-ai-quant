from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.intelligence.multitimeframe import MultiTimeframeAssessment


@dataclass(frozen=True)
class ExplanationFactor:
    name: str
    contribution: float
    detail: str


@dataclass(frozen=True)
class TradeExplanation:
    symbol: str
    action: str
    confidence: float
    summary: str
    factors: tuple[ExplanationFactor, ...]
    risks: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        return payload


class TradeExplanationBuilder:
    """Construct deterministic explanations from scored evidence."""

    def build(
        self,
        assessment: MultiTimeframeAssessment,
        *,
        regime: str,
        model_probability: float | None = None,
        risk_reward_ratio: float | None = None,
        extra_factors: Mapping[str, float] | None = None,
    ) -> TradeExplanation:
        if assessment.aggregate_score > 0.15:
            action = "BUY"
        elif assessment.aggregate_score < -0.15:
            action = "SELL"
        else:
            action = "HOLD"
        factors = [
            ExplanationFactor(
                "multi_timeframe",
                assessment.aggregate_score,
                (
                    f"{assessment.entry_quality.value} alignment with "
                    f"{assessment.confirmation_score:.0%} confirmation"
                ),
            ),
            ExplanationFactor(
                "regime",
                0.10 if regime not in {"panic", "volatility_expansion"} else -0.20,
                f"market regime: {regime}",
            ),
        ]
        if model_probability is not None:
            factors.append(
                ExplanationFactor(
                    "model_probability",
                    model_probability - 0.5,
                    f"model probability {model_probability:.1%}",
                )
            )
        for name, value in (extra_factors or {}).items():
            factors.append(
                ExplanationFactor(name, float(value), f"{name} contribution {value:+.3f}")
            )
        positive = sum(max(0.0, factor.contribution) for factor in factors)
        negative = sum(abs(min(0.0, factor.contribution)) for factor in factors)
        confidence = max(0.0, min(1.0, 0.5 + positive * 0.35 - negative * 0.35))
        risks = [f"timeframe conflict {assessment.conflict_score:.0%}"]
        if risk_reward_ratio is not None:
            risks.append(f"estimated reward/risk {risk_reward_ratio:.2f}")
        if assessment.conflict_score > 0.40:
            risks.append("material timeframe disagreement")
        rejected = () if assessment.trading_allowed else assessment.reasons
        summary = (
            f"{action} {assessment.symbol}: "
            f"{assessment.direction.value.replace('_', ' ')} "
            f"with {confidence:.0%} confidence"
        )
        return TradeExplanation(
            assessment.symbol,
            action,
            confidence,
            summary,
            tuple(factors),
            tuple(risks),
            tuple(rejected),
            datetime.now(UTC),
        )


class ExplanationJournal:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, explanation: TradeExplanation) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(explanation.to_dict(), sort_keys=True) + "\n")

    def load(self, limit: int | None = None) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return rows[-limit:] if limit is not None else rows
