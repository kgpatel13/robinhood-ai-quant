from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from src.continuous_portfolio.models import (
    PaperPortfolioSnapshot,
    StrategyAction,
    StrategyHealth,
    StrategyObservation,
)


@dataclass(frozen=True)
class StrategyHealthPolicy:
    promote_score: float = 80.0
    reduce_score: float = 55.0
    pause_score: float = 35.0
    maximum_drawdown: float = 0.20
    minimum_trades_for_promotion: int = 20


class ContinuousPaperPortfolio:
    """In-memory paper portfolio monitor with deterministic strategy health scoring."""

    def __init__(self, policy: StrategyHealthPolicy | None = None) -> None:
        self.policy = policy or StrategyHealthPolicy()
        self._observations: dict[str, list[StrategyObservation]] = defaultdict(list)

    def record(self, observation: StrategyObservation) -> None:
        if observation.equity <= 0:
            raise ValueError("equity must be positive")
        history = self._observations[observation.strategy]
        if history and observation.timestamp <= history[-1].timestamp:
            raise ValueError("observations must be recorded in chronological order")
        history.append(observation)

    def snapshot(self, as_of: datetime | None = None) -> PaperPortfolioSnapshot:
        health = tuple(
            sorted(
                (
                    self._health(strategy, history)
                    for strategy, history in self._observations.items()
                ),
                key=lambda item: item.score,
                reverse=True,
            )
        )
        champion = next(
            (item.strategy for item in health if item.action is StrategyAction.PROMOTE), None
        )
        aggregate_equity = sum(history[-1].equity for history in self._observations.values())
        return PaperPortfolioSnapshot(
            as_of=as_of or datetime.now(UTC),
            strategies=health,
            champion=champion,
            aggregate_equity=aggregate_equity,
        )

    def _health(
        self, strategy: str, history: list[StrategyObservation]
    ) -> StrategyHealth:
        initial = history[0].equity
        latest = history[-1]
        total_return = latest.equity / initial - 1.0
        peak = history[0].equity
        maximum_drawdown = 0.0
        for observation in history:
            peak = max(peak, observation.equity)
            maximum_drawdown = min(maximum_drawdown, observation.equity / peak - 1.0)
        slippage_gap = max(
            latest.realized_slippage_bps - latest.expected_slippage_bps, 0.0
        )
        slippage_quality = max(0.0, 1.0 - slippage_gap / 20.0)
        return_quality = min(1.0, max(0.0, 0.5 + total_return * 2.0))
        drawdown_quality = max(
            0.0, 1.0 - abs(maximum_drawdown) / self.policy.maximum_drawdown
        )
        trade_quality = min(1.0, latest.trade_count / self.policy.minimum_trades_for_promotion)
        score = 100.0 * (
            0.40 * return_quality
            + 0.30 * drawdown_quality
            + 0.15 * slippage_quality
            + 0.15 * trade_quality
        )
        reasons: list[str] = []
        if abs(maximum_drawdown) > self.policy.maximum_drawdown:
            reasons.append("drawdown_limit_breached")
        if latest.trade_count < self.policy.minimum_trades_for_promotion:
            reasons.append("insufficient_paper_trades")
        if slippage_quality < 0.5:
            reasons.append("execution_quality_deteriorated")
        action = self._action(score, reasons)
        return StrategyHealth(
            strategy=strategy,
            score=float(score),
            action=action,
            total_return=float(total_return),
            maximum_drawdown=float(maximum_drawdown),
            slippage_quality=float(slippage_quality),
            trade_count=latest.trade_count,
            reasons=tuple(reasons),
        )

    def _action(self, score: float, reasons: list[str]) -> StrategyAction:
        if "drawdown_limit_breached" in reasons or score < self.policy.pause_score:
            return StrategyAction.PAUSE
        if score < self.policy.reduce_score:
            return StrategyAction.REDUCE
        if score >= self.policy.promote_score and not reasons:
            return StrategyAction.PROMOTE
        return StrategyAction.CONTINUE
