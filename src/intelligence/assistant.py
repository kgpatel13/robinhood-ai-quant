from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantContext:
    positions: Sequence[Mapping[str, object]] = ()
    trades: Sequence[Mapping[str, object]] = ()
    strategies: Sequence[Mapping[str, object]] = ()
    explanations: Sequence[Mapping[str, object]] = ()
    performance: Mapping[str, object] | None = None


@dataclass(frozen=True)
class AssistantAnswer:
    intent: str
    answer: str
    evidence_count: int


class AtlasAssistant:
    """Deterministic, local query layer over Atlas records; no external LLM required."""

    def answer(self, question: str, context: AssistantContext) -> AssistantAnswer:
        normalized = " ".join(question.lower().split())
        if any(token in normalized for token in ("why", "explain", "reason")):
            return self._explain(normalized, context)
        if any(token in normalized for token in ("losing", "loss", "down")):
            return self._losers(context)
        if "position" in normalized or "holding" in normalized:
            return self._positions(context)
        if "strategy" in normalized and any(
            token in normalized for token in ("underperform", "worst", "weak")
        ):
            return self._strategies(context)
        if any(token in normalized for token in ("performance", "return", "drawdown", "sharpe")):
            return self._performance(context)
        return AssistantAnswer(
            "help",
            (
                "I can summarize positions, losing positions, performance, weak "
                "strategies, or explain a recorded trade decision."
            ),
            0,
        )

    def _explain(self, question: str, context: AssistantContext) -> AssistantAnswer:
        symbol = next(
            (
                token.upper()
                for token in question.replace("?", "").split()
                if token.isalpha() and 1 < len(token) <= 6
            ),
            "",
        )
        candidates = [
            row
            for row in context.explanations
            if not symbol or str(row.get("symbol", "")).upper() == symbol
        ]
        if not candidates:
            return AssistantAnswer("explanation", "No matching explanation is recorded yet.", 0)
        row = candidates[-1]
        risks_value = row.get("risks", ())
        risks = (
            ", ".join(str(item) for item in risks_value)
            if isinstance(risks_value, Iterable)
            and not isinstance(risks_value, (str, bytes, Mapping))
            else str(risks_value)
        )
        summary = str(row.get("summary", "Decision recorded"))
        return AssistantAnswer(
            "explanation",
            f"{summary}. Risks: {risks}",
            1,
        )

    def _losers(self, context: AssistantContext) -> AssistantAnswer:
        losers = [
            row
            for row in context.positions
            if self._to_float(row.get("unrealized_pnl", row.get("pnl", 0.0))) < 0
        ]
        if not losers:
            return AssistantAnswer(
                "losers",
                "No losing open positions are present in the supplied context.",
                0,
            )
        text = "; ".join(
            (
                f"{row.get('symbol', '?')}: "
                f"${self._to_float(row.get('unrealized_pnl', row.get('pnl', 0.0))):,.2f}"
            )
            for row in losers
        )
        return AssistantAnswer("losers", f"Losing positions: {text}", len(losers))

    def _positions(self, context: AssistantContext) -> AssistantAnswer:
        if not context.positions:
            return AssistantAnswer(
                "positions", "There are no open positions in the supplied context.", 0
            )
        text = "; ".join(
            (f"{row.get('symbol', '?')} qty {row.get('quantity', row.get('qty', '?'))}")
            for row in context.positions
        )
        return AssistantAnswer("positions", f"Open positions: {text}", len(context.positions))

    def _strategies(self, context: AssistantContext) -> AssistantAnswer:
        if not context.strategies:
            return AssistantAnswer(
                "strategies", "No strategy performance records are available.", 0
            )
        ordered = sorted(
            context.strategies,
            key=lambda row: self._to_float(row.get("return", row.get("total_return", 0.0))),
        )
        row = ordered[0]
        name = row.get("strategy", row.get("name", "?"))
        strategy_return = self._to_float(row.get("return", row.get("total_return", 0.0)))
        return AssistantAnswer(
            "strategies",
            f"Weakest recorded strategy: {name} with return {strategy_return:.2%}.",
            1,
        )

    def _performance(self, context: AssistantContext) -> AssistantAnswer:
        if not context.performance:
            return AssistantAnswer("performance", "No performance summary is available.", 0)
        items = ", ".join(
            f"{key.replace('_', ' ')}: {value}" for key, value in context.performance.items()
        )
        return AssistantAnswer(
            "performance",
            f"Performance summary — {items}",
            len(context.performance),
        )

    @staticmethod
    def _to_float(value: object) -> float:
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float, str, bytes, bytearray)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
        return 0.0
