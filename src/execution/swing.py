from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from src.execution.models import AccountSnapshot, OrderRequest, OrderSide


class SwingExitReason(StrEnum):
    MAX_HOLD = "max_hold"
    STOP_LOSS = "stop_loss"
    PROFIT_TARGET = "profit_target"
    TRAILING_STOP = "trailing_stop"


@dataclass(frozen=True)
class SwingPositionState:
    symbol: str
    entry_date: date
    entry_price: float
    highest_price: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.entry_price <= 0 or self.highest_price <= 0:
            raise ValueError("swing prices must be positive")


@dataclass(frozen=True)
class ShortSwingConfig:
    max_holding_days: int = 5
    stop_loss: float = 0.05
    profit_target: float = 0.10
    trailing_stop: float = 0.04
    max_trades_per_day: int = 5
    max_simultaneous_positions: int = 5

    def __post_init__(self) -> None:
        if self.max_holding_days < 1:
            raise ValueError("max_holding_days must be positive")
        for name in ("stop_loss", "profit_target", "trailing_stop"):
            value = float(getattr(self, name))
            if not 0 < value < 1:
                raise ValueError(f"{name} must be in (0, 1)")
        if self.max_trades_per_day < 1 or self.max_simultaneous_positions < 1:
            raise ValueError("trade and position limits must be positive")


@dataclass(frozen=True)
class SwingExitDecision:
    order: OrderRequest
    reason: SwingExitReason
    holding_days: int
    return_since_entry: float


class ShortSwingLifecycle:
    def __init__(self, config: ShortSwingConfig | None = None) -> None:
        self.config = config or ShortSwingConfig()

    def evaluate_exits(
        self,
        account: AccountSnapshot,
        states: dict[str, SwingPositionState],
        prices: dict[str, float],
        trading_date: date,
    ) -> tuple[SwingExitDecision, ...]:
        exits: list[SwingExitDecision] = []
        for position in account.positions:
            state = states.get(position.symbol)
            price = prices.get(position.symbol)
            if state is None or price is None or price <= 0:
                continue
            holding_days = max(0, (trading_date - state.entry_date).days)
            highest = max(state.highest_price, price)
            gain = price / state.entry_price - 1.0
            trailing_drawdown = price / highest - 1.0
            reason: SwingExitReason | None = None
            if holding_days >= self.config.max_holding_days:
                reason = SwingExitReason.MAX_HOLD
            elif gain <= -self.config.stop_loss:
                reason = SwingExitReason.STOP_LOSS
            elif gain >= self.config.profit_target:
                reason = SwingExitReason.PROFIT_TARGET
            elif trailing_drawdown <= -self.config.trailing_stop:
                reason = SwingExitReason.TRAILING_STOP
            if reason is None:
                continue
            exits.append(
                SwingExitDecision(
                    OrderRequest(
                        position.symbol,
                        position.quantity,
                        OrderSide.SELL,
                        client_order_id=(
                            f"swing-exit:{trading_date.isoformat()}:{position.symbol}:{reason.value}"
                        ),
                    ),
                    reason,
                    holding_days,
                    gain,
                )
            )
        return tuple(exits)

    def filter_entry_orders(
        self,
        orders: tuple[OrderRequest, ...],
        account: AccountSnapshot,
        *,
        trades_submitted_today: int = 0,
    ) -> tuple[OrderRequest, ...]:
        if trades_submitted_today < 0:
            raise ValueError("trades_submitted_today cannot be negative")
        remaining_trades = max(0, self.config.max_trades_per_day - trades_submitted_today)
        open_symbols = {position.symbol for position in account.positions if position.quantity > 0}
        remaining_slots = max(0, self.config.max_simultaneous_positions - len(open_symbols))
        accepted: list[OrderRequest] = []
        for order in orders:
            if order.side is OrderSide.SELL:
                accepted.append(order)
                continue
            if remaining_trades <= 0:
                continue
            is_new_position = order.symbol not in open_symbols
            if is_new_position and remaining_slots <= 0:
                continue
            accepted.append(order)
            remaining_trades -= 1
            if is_new_position:
                open_symbols.add(order.symbol)
                remaining_slots -= 1
        return tuple(accepted)


class SwingCheckpointJournal(Protocol):
    def save_checkpoint(self, key: str, payload: dict[str, Any]) -> None: ...

    def load_checkpoint(self, key: str) -> dict[str, Any] | None: ...


class SwingPositionStore:
    CHECKPOINT_KEY = "short-swing-position-states"

    def __init__(self, journal: SwingCheckpointJournal) -> None:
        self.journal = journal

    def save(self, states: dict[str, SwingPositionState]) -> None:
        self.journal.save_checkpoint(
            self.CHECKPOINT_KEY,
            {
                symbol: {
                    "symbol": state.symbol,
                    "entry_date": state.entry_date.isoformat(),
                    "entry_price": state.entry_price,
                    "highest_price": state.highest_price,
                }
                for symbol, state in states.items()
            },
        )

    def load(self) -> dict[str, SwingPositionState]:
        payload = self.journal.load_checkpoint(self.CHECKPOINT_KEY)
        if payload is None:
            return {}
        return {
            str(symbol): SwingPositionState(
                symbol=str(item["symbol"]),
                entry_date=date.fromisoformat(str(item["entry_date"])),
                entry_price=float(item["entry_price"]),
                highest_price=float(item["highest_price"]),
            )
            for symbol, item in payload.items()
            if isinstance(item, dict)
        }
