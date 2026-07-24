from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AssetClass = Literal["stock", "crypto"]


@dataclass(frozen=True)
class MarketProfile:
    asset_class: AssetClass
    minimum_price: float
    minimum_dollar_volume: float
    maximum_spread_bps: float
    minimum_history: int
    entry_score: float
    strong_entry_score: float
    max_positions: int
    risk_per_trade: float
    stop_atr_multiple: float
    target_atr_multiple: float
    maximum_position_weight: float

    def __post_init__(self) -> None:
        if self.minimum_price <= 0 or self.minimum_dollar_volume < 0:
            raise ValueError("Price and liquidity limits must be non-negative")
        if not 0 <= self.entry_score <= self.strong_entry_score <= 100:
            raise ValueError("Entry scores must satisfy 0 <= entry <= strong <= 100")
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if not 0 < self.risk_per_trade <= 0.05:
            raise ValueError("risk_per_trade must be in (0, 0.05]")
        if not 0 < self.maximum_position_weight <= 1:
            raise ValueError("maximum_position_weight must be in (0, 1]")


@dataclass(frozen=True)
class Phase9Config:
    symbols: tuple[str, ...] = ()
    stock_profile: MarketProfile = field(
        default_factory=lambda: MarketProfile(
            asset_class="stock",
            minimum_price=3.0,
            minimum_dollar_volume=5_000_000.0,
            maximum_spread_bps=35.0,
            minimum_history=220,
            entry_score=62.0,
            strong_entry_score=75.0,
            max_positions=8,
            risk_per_trade=0.005,
            stop_atr_multiple=1.5,
            target_atr_multiple=2.4,
            maximum_position_weight=0.15,
        )
    )
    crypto_profile: MarketProfile = field(
        default_factory=lambda: MarketProfile(
            asset_class="crypto",
            minimum_price=0.000001,
            minimum_dollar_volume=1_000_000.0,
            maximum_spread_bps=100.0,
            minimum_history=180,
            entry_score=64.0,
            strong_entry_score=78.0,
            max_positions=5,
            risk_per_trade=0.004,
            stop_atr_multiple=2.0,
            target_atr_multiple=3.0,
            maximum_position_weight=0.12,
        )
    )
    top_n_per_market: int = 25
    account_equity: float = 100_000.0
    maximum_total_exposure: float = 0.85
    maximum_daily_loss: float = 0.02
    news_risk_default: float = 0.0
    output_root: Path = Path("reports/phase9")

    def __post_init__(self) -> None:
        if self.top_n_per_market < 1:
            raise ValueError("top_n_per_market must be positive")
        if self.account_equity <= 0:
            raise ValueError("account_equity must be positive")
        if not 0 < self.maximum_total_exposure <= 1:
            raise ValueError("maximum_total_exposure must be in (0, 1]")
        if not 0 < self.maximum_daily_loss <= 0.1:
            raise ValueError("maximum_daily_loss must be in (0, 0.1]")
        if not 0 <= self.news_risk_default <= 1:
            raise ValueError("news_risk_default must be in [0, 1]")


@dataclass(frozen=True)
class Phase9Result:
    scanned: int
    eligible: int
    stock_opportunities: int
    crypto_opportunities: int
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
