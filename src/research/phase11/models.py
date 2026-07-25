from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Phase11Config:
    data_root: Path = Path("data/validated")
    dataset_path: Path = Path("data/ml_dataset/training_dataset.parquet")
    output_root: Path = Path("reports/phase11_dataset")
    symbols: tuple[str, ...] = ()
    asset_classes: tuple[str, ...] = ("stock", "crypto")
    holding_periods: tuple[int, ...] = (1, 3, 5, 10, 20)
    warmup_bars: int = 220
    observation_stride: int = 1
    slippage_bps: float = 5.0
    spread_bps: float = 8.0
    fee_bps: float = 0.0
    risk_penalty: float = 0.5

    def __post_init__(self) -> None:
        allowed = {"stock", "etf", "crypto"}
        if not self.asset_classes or not set(self.asset_classes) <= allowed:
            raise ValueError("asset_classes must contain stock, etf, and/or crypto")
        if not self.holding_periods or any(value < 1 for value in self.holding_periods):
            raise ValueError("holding_periods must contain positive integers")
        if len(set(self.holding_periods)) != len(self.holding_periods):
            raise ValueError("holding_periods cannot contain duplicates")
        if self.warmup_bars < 220:
            raise ValueError("warmup_bars must be at least 220")
        if self.observation_stride < 1:
            raise ValueError("observation_stride must be positive")
        if min(self.slippage_bps, self.spread_bps, self.fee_bps) < 0:
            raise ValueError("execution costs cannot be negative")
        if self.risk_penalty < 0:
            raise ValueError("risk_penalty cannot be negative")


@dataclass(frozen=True)
class Phase11Result:
    scanned_files: int
    included_symbols: int
    rows: int
    output: str
    dataset: str
    audit_passed: bool
    artifacts: dict[str, str] = field(default_factory=dict)
