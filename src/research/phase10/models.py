from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AssetClass = Literal["stock", "etf", "crypto"]
ExitReason = Literal["target", "stop", "time", "ambiguous"]


@dataclass(frozen=True)
class ReplayProfile:
    asset_class: AssetClass
    minimum_history: int
    entry_score: float
    score_bands: tuple[float, ...]
    holding_periods: tuple[int, ...]
    stop_atr_multiple: float
    target_atr_multiple: float
    slippage_bps: float
    spread_bps: float
    fee_bps: float
    minimum_trades_per_band: int = 20

    def __post_init__(self) -> None:
        if self.minimum_history < 220:
            raise ValueError("minimum_history must be at least 220")
        if not 0 <= self.entry_score <= 100:
            raise ValueError("entry_score must be in [0, 100]")
        if len(self.score_bands) < 2 or tuple(sorted(self.score_bands)) != self.score_bands:
            raise ValueError("score_bands must be sorted and contain at least two values")
        if self.score_bands[0] < 0 or self.score_bands[-1] > 101:
            raise ValueError("score_bands must be within [0, 101]")
        if not self.holding_periods or any(period < 1 for period in self.holding_periods):
            raise ValueError("holding_periods must be positive")
        if self.stop_atr_multiple <= 0 or self.target_atr_multiple <= 0:
            raise ValueError("ATR multiples must be positive")
        if min(self.slippage_bps, self.spread_bps, self.fee_bps) < 0:
            raise ValueError("execution costs cannot be negative")
        if self.minimum_trades_per_band < 1:
            raise ValueError("minimum_trades_per_band must be positive")


@dataclass(frozen=True)
class Phase10Config:
    symbols: tuple[str, ...] = ()
    etf_symbols: tuple[str, ...] = (
        "DIA",
        "EEM",
        "GLD",
        "IWM",
        "QQQ",
        "SCHD",
        "SLV",
        "SPY",
        "TLT",
        "VGT",
        "VOO",
        "VTI",
        "VXUS",
        "XLE",
        "XLF",
        "XLK",
    )
    stock_profile: ReplayProfile = field(
        default_factory=lambda: ReplayProfile(
            asset_class="stock",
            minimum_history=260,
            entry_score=62.0,
            score_bands=(0.0, 50.0, 55.0, 60.0, 62.0, 65.0, 70.0, 75.0, 101.0),
            holding_periods=(1, 3, 5, 10, 20),
            stop_atr_multiple=1.5,
            target_atr_multiple=2.4,
            slippage_bps=5.0,
            spread_bps=8.0,
            fee_bps=0.0,
        )
    )
    crypto_profile: ReplayProfile = field(
        default_factory=lambda: ReplayProfile(
            asset_class="crypto",
            minimum_history=220,
            entry_score=64.0,
            score_bands=(0.0, 40.0, 45.0, 50.0, 55.0, 60.0, 64.0, 70.0, 78.0, 101.0),
            holding_periods=(1, 3, 5, 10, 20),
            stop_atr_multiple=2.0,
            target_atr_multiple=3.0,
            slippage_bps=10.0,
            spread_bps=15.0,
            fee_bps=10.0,
        )
    )
    warmup_bars: int = 220
    signal_stride: int = 1
    primary_holding_period: int = 5
    same_bar_policy: Literal["conservative", "optimistic", "ambiguous"] = "conservative"
    include_below_threshold: bool = True
    portfolio_initial_capital: float = 100_000.0
    portfolio_risk_per_trade: float = 0.01
    portfolio_maximum_position_percent: float = 0.10
    portfolio_maximum_concurrent_positions: int = 10
    portfolio_one_position_per_symbol: bool = True
    portfolio_cooldown_bars_after_exit: int = 1
    walk_forward_train_end_year: int = 2022
    walk_forward_validation_end_year: int = 2024
    rolling_train_years: int = 5
    rolling_validation_years: int = 1
    rolling_test_years: int = 1
    rolling_step_years: int = 1
    promotion_minimum_profitable_window_fraction: float = 0.60
    promotion_minimum_median_profit_factor: float = 1.10
    promotion_minimum_test_trades: int = 100
    promotion_maximum_threshold_range: float = 15.0
    final_minimum_recent_average_return: float = 0.0
    final_minimum_bootstrap_positive_probability: float = 0.60
    final_minimum_cross_sectional_top_quantile_lift: float = 0.0
    final_minimum_feature_stability_fraction: float = 0.50
    bootstrap_samples: int = 1000
    output_root: Path = Path("reports/phase10")

    def __post_init__(self) -> None:
        if self.warmup_bars < 220:
            raise ValueError("warmup_bars must be at least 220")
        if self.signal_stride < 1:
            raise ValueError("signal_stride must be positive")
        periods = set(self.stock_profile.holding_periods) & set(self.crypto_profile.holding_periods)
        if self.primary_holding_period not in periods:
            raise ValueError("primary_holding_period must exist in both profiles")
        if self.portfolio_initial_capital <= 0:
            raise ValueError("portfolio_initial_capital must be positive")
        if not 0 < self.portfolio_risk_per_trade <= 1:
            raise ValueError("portfolio_risk_per_trade must be in (0, 1]")
        if not 0 < self.portfolio_maximum_position_percent <= 1:
            raise ValueError("portfolio_maximum_position_percent must be in (0, 1]")
        if self.portfolio_maximum_concurrent_positions < 1:
            raise ValueError("portfolio_maximum_concurrent_positions must be positive")
        if self.portfolio_cooldown_bars_after_exit < 0:
            raise ValueError("portfolio_cooldown_bars_after_exit cannot be negative")
        if self.walk_forward_train_end_year >= self.walk_forward_validation_end_year:
            raise ValueError("walk-forward train year must precede validation year")
        if (
            min(
                self.rolling_train_years,
                self.rolling_validation_years,
                self.rolling_test_years,
                self.rolling_step_years,
            )
            < 1
        ):
            raise ValueError("rolling walk-forward periods must be positive")
        if not 0 < self.promotion_minimum_profitable_window_fraction <= 1:
            raise ValueError("promotion window fraction must be in (0, 1]")
        if self.promotion_minimum_median_profit_factor <= 1:
            raise ValueError("promotion profit factor must be greater than 1")
        if self.promotion_minimum_test_trades < 1:
            raise ValueError("promotion minimum test trades must be positive")
        if self.promotion_maximum_threshold_range < 0:
            raise ValueError("promotion threshold range cannot be negative")
        if not 0 <= self.final_minimum_bootstrap_positive_probability <= 1:
            raise ValueError("bootstrap probability must be in [0, 1]")
        if not 0 <= self.final_minimum_feature_stability_fraction <= 1:
            raise ValueError("feature stability fraction must be in [0, 1]")
        if self.bootstrap_samples < 100:
            raise ValueError("bootstrap_samples must be at least 100")


@dataclass(frozen=True)
class Phase10Result:
    scanned_symbols: int
    replayed_signals: int
    threshold_signals: int
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
