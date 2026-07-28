from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from src.execution.models import AccountSnapshot


class ProtectionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    LOCKED = "locked"


class ProtectionReason(StrEnum):
    CLEAR = "clear"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    PORTFOLIO_HEAT_LIMIT = "portfolio_heat_limit"
    CONSECUTIVE_LOSS_LIMIT = "consecutive_loss_limit"
    MANUAL_LOCK = "manual_lock"


@dataclass(frozen=True)
class AccountProtectionConfig:
    max_daily_loss: float = 0.03
    max_weekly_loss: float = 0.06
    max_drawdown: float = 0.15
    max_portfolio_heat: float = 0.08
    max_consecutive_losses: int = 4

    def __post_init__(self) -> None:
        for name in ("max_daily_loss", "max_weekly_loss", "max_drawdown", "max_portfolio_heat"):
            value = float(getattr(self, name))
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be positive")


@dataclass(frozen=True)
class AccountProtectionState:
    trading_date: date
    start_of_day_equity: float
    start_of_week_equity: float
    high_water_mark: float
    consecutive_losses: int = 0
    manual_lock: bool = False

    def __post_init__(self) -> None:
        if min(self.start_of_day_equity, self.start_of_week_equity, self.high_water_mark) <= 0:
            raise ValueError("protection equity references must be positive")
        if self.consecutive_losses < 0:
            raise ValueError("consecutive_losses cannot be negative")


@dataclass(frozen=True)
class ProtectionDecision:
    status: ProtectionStatus
    reason: ProtectionReason
    daily_return: float
    weekly_return: float
    drawdown: float
    portfolio_heat: float
    details: str = ""

    @property
    def trading_allowed(self) -> bool:
        return self.status is ProtectionStatus.ACTIVE


class AccountProtectionEngine:
    def __init__(self, config: AccountProtectionConfig | None = None) -> None:
        self.config = config or AccountProtectionConfig()

    def evaluate(
        self,
        account: AccountSnapshot,
        state: AccountProtectionState,
        *,
        portfolio_heat: float = 0.0,
    ) -> ProtectionDecision:
        if portfolio_heat < 0:
            raise ValueError("portfolio_heat cannot be negative")
        daily_return = account.equity / state.start_of_day_equity - 1.0
        weekly_return = account.equity / state.start_of_week_equity - 1.0
        drawdown = account.equity / max(state.high_water_mark, account.equity) - 1.0

        if state.manual_lock:
            return self._decision(
                ProtectionStatus.LOCKED,
                ProtectionReason.MANUAL_LOCK,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        if daily_return <= -self.config.max_daily_loss:
            return self._decision(
                ProtectionStatus.PAUSED,
                ProtectionReason.DAILY_LOSS_LIMIT,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        if weekly_return <= -self.config.max_weekly_loss:
            return self._decision(
                ProtectionStatus.PAUSED,
                ProtectionReason.WEEKLY_LOSS_LIMIT,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        if drawdown <= -self.config.max_drawdown:
            return self._decision(
                ProtectionStatus.LOCKED,
                ProtectionReason.DRAWDOWN_LIMIT,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        if portfolio_heat >= self.config.max_portfolio_heat:
            return self._decision(
                ProtectionStatus.PAUSED,
                ProtectionReason.PORTFOLIO_HEAT_LIMIT,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        if state.consecutive_losses >= self.config.max_consecutive_losses:
            return self._decision(
                ProtectionStatus.PAUSED,
                ProtectionReason.CONSECUTIVE_LOSS_LIMIT,
                daily_return,
                weekly_return,
                drawdown,
                portfolio_heat,
            )
        return self._decision(
            ProtectionStatus.ACTIVE,
            ProtectionReason.CLEAR,
            daily_return,
            weekly_return,
            drawdown,
            portfolio_heat,
        )

    @staticmethod
    def _decision(
        status: ProtectionStatus,
        reason: ProtectionReason,
        daily_return: float,
        weekly_return: float,
        drawdown: float,
        portfolio_heat: float,
    ) -> ProtectionDecision:
        return ProtectionDecision(
            status,
            reason,
            daily_return,
            weekly_return,
            drawdown,
            portfolio_heat,
            f"daily={daily_return:.4f};weekly={weekly_return:.4f};"
            f"drawdown={drawdown:.4f};heat={portfolio_heat:.4f}",
        )


class ProtectionCheckpointJournal(Protocol):
    def save_checkpoint(self, key: str, payload: dict[str, Any]) -> None: ...

    def load_checkpoint(self, key: str) -> dict[str, Any] | None: ...


class AccountProtectionStore:
    CHECKPOINT_KEY = "account-protection-state"

    def __init__(self, journal: ProtectionCheckpointJournal) -> None:
        self.journal = journal

    def save(self, state: AccountProtectionState) -> None:
        self.journal.save_checkpoint(
            self.CHECKPOINT_KEY,
            {
                "trading_date": state.trading_date.isoformat(),
                "start_of_day_equity": state.start_of_day_equity,
                "start_of_week_equity": state.start_of_week_equity,
                "high_water_mark": state.high_water_mark,
                "consecutive_losses": state.consecutive_losses,
                "manual_lock": state.manual_lock,
            },
        )

    def load(self) -> AccountProtectionState | None:
        payload = self.journal.load_checkpoint(self.CHECKPOINT_KEY)
        if payload is None:
            return None
        return AccountProtectionState(
            trading_date=date.fromisoformat(str(payload["trading_date"])),
            start_of_day_equity=float(payload["start_of_day_equity"]),
            start_of_week_equity=float(payload["start_of_week_equity"]),
            high_water_mark=float(payload["high_water_mark"]),
            consecutive_losses=int(payload.get("consecutive_losses", 0)),
            manual_lock=bool(payload.get("manual_lock", False)),
        )
