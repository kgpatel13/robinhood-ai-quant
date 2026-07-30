from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AssetClass(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"


class ExitReason(StrEnum):
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    SIGNAL_INVALIDATION = "signal_invalidation"
    NO_PROGRESS = "no_progress"
    ROTATION = "rotation"
    MAX_HOLD = "max_hold"
    END_OF_TEST = "end_of_test"


@dataclass(frozen=True)
class RotationConfig:
    initial_cash: float = 5000.0
    max_positions: int = 4
    min_hold_days: int = 1
    preferred_max_hold_days: int = 10
    max_hold_days: int = 30
    risk_per_trade_pct: float = 0.005
    max_position_pct: float = 0.25
    max_crypto_position_pct: float = 0.12
    total_crypto_pct: float = 0.25
    cash_reserve_pct: float = 0.10
    min_entry_score: float = 0.62
    rotation_score_improvement: float = 0.12
    stop_atr_multiple: float = 1.8
    trailing_atr_multiple: float = 2.2
    no_progress_days: int = 7
    no_progress_return: float = 0.005
    slippage_bps_stock: float = 5.0
    slippage_bps_crypto: float = 10.0
    commission_per_order: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if not 0 <= self.min_hold_days <= self.preferred_max_hold_days <= self.max_hold_days:
            raise ValueError("holding periods must be ordered")
        for name in (
            "risk_per_trade_pct",
            "max_position_pct",
            "max_crypto_position_pct",
            "total_crypto_pct",
            "cash_reserve_pct",
        ):
            value = float(getattr(self, name))
            if not 0 <= value < 1:
                raise ValueError(f"{name} must be in [0, 1)")
        if not 0 <= self.min_entry_score <= 1:
            raise ValueError("min_entry_score must be in [0, 1]")
        if not 0 <= self.rotation_score_improvement <= 1:
            raise ValueError("rotation_score_improvement must be in [0, 1]")


@dataclass(frozen=True)
class Opportunity:
    timestamp: datetime
    symbol: str
    asset_class: AssetClass
    strategy: str
    score: float
    expected_holding_days: int
    expected_return: float
    volatility: float
    atr: float
    price: float
    components: Mapping[str, float] = field(default_factory=dict)

    @property
    def capital_efficiency(self) -> float:
        risk = max(self.volatility, 1e-6)
        days = max(self.expected_holding_days, 1)
        return self.expected_return / (risk * days)


@dataclass
class Position:
    symbol: str
    asset_class: AssetClass
    strategy: str
    entry_time: datetime
    entry_price: float
    quantity: float
    entry_score: float
    expected_holding_days: int
    stop_price: float
    trailing_stop: float
    highest_price: float
    last_score: float
    days_held: int = 0

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_return(self, price: float) -> float:
        return price / self.entry_price - 1.0


@dataclass(frozen=True)
class RotationTrade:
    symbol: str
    asset_class: AssetClass
    strategy: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    costs: float
    net_pnl: float
    holding_days: int
    exit_reason: ExitReason


@dataclass(frozen=True)
class RotationBacktestResult:
    metrics: Mapping[str, float | int]
    trades: tuple[RotationTrade, ...]
    equity_curve: tuple[tuple[datetime, float], ...]
    decisions: tuple[Mapping[str, object], ...]
