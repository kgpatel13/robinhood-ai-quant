from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.control_center.config import RiskLimits
from src.control_center.models import CandidateStatus, IntradaySessionState, RankedCandidate


@dataclass(frozen=True)
class AllocationDecision:
    candidate: RankedCandidate
    approved: bool
    approved_weight: float
    reasons: tuple[str, ...]


class IntradayPortfolioRiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate(
        self,
        candidate: RankedCandidate,
        state: IntradaySessionState,
        *,
        as_of: datetime,
    ) -> AllocationDecision:
        reasons: list[str] = list(candidate.reasons)
        if candidate.status is not CandidateStatus.ELIGIBLE:
            reasons.append("candidate not eligible")
        if state.halted:
            reasons.append(f"session halted: {state.halt_reason}")
        if state.trades_today >= self.limits.maximum_trades_per_day:
            reasons.append("daily trade limit reached")
        if len(state.positions) >= self.limits.maximum_open_positions:
            reasons.append("open-position limit reached")
        if candidate.symbol in state.positions:
            reasons.append("symbol already held")
        cooldown = state.cooldown_until.get(candidate.symbol)
        if cooldown is not None and cooldown > as_of:
            reasons.append("symbol cooldown active")
        loss_fraction = max(0.0, -state.realized_pnl / state.starting_equity)
        if loss_fraction >= self.limits.maximum_daily_loss_fraction:
            reasons.append("maximum daily loss reached")
        if state.consecutive_losses >= self.limits.maximum_consecutive_losses:
            reasons.append("consecutive-loss cutoff reached")
        deployed = sum(position.market_value for position in state.positions.values())
        deployed_fraction = deployed / state.starting_equity
        remaining = max(0.0, self.limits.maximum_deployed_fraction - deployed_fraction)
        sector_value = sum(
            position.market_value
            for position in state.positions.values()
            if position.sector == candidate.sector
        )
        sector_remaining = max(
            0.0,
            self.limits.maximum_sector_fraction - sector_value / state.starting_equity,
        )
        approved_weight = min(
            candidate.suggested_weight,
            self.limits.maximum_position_fraction,
            remaining,
            sector_remaining,
        )
        if approved_weight <= 0:
            reasons.append("portfolio exposure capacity exhausted")
        return AllocationDecision(
            candidate, not reasons, approved_weight if not reasons else 0.0, tuple(reasons)
        )

    def register_loss_cooldown(
        self, state: IntradaySessionState, symbol: str, *, as_of: datetime
    ) -> None:
        state.cooldown_until[symbol] = as_of + timedelta(minutes=self.limits.cooldown_minutes)
