from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class RiskLimits:
    maximum_deployed_fraction: float = 0.40
    maximum_position_fraction: float = 0.08
    maximum_sector_fraction: float = 0.20
    maximum_open_positions: int = 5
    maximum_trades_per_day: int = 12
    maximum_daily_loss_fraction: float = 0.015
    maximum_consecutive_losses: int = 4
    cooldown_minutes: int = 30

    def __post_init__(self) -> None:
        fractions = (
            self.maximum_deployed_fraction,
            self.maximum_position_fraction,
            self.maximum_sector_fraction,
            self.maximum_daily_loss_fraction,
        )
        if any(value <= 0 or value > 1 for value in fractions):
            raise ValueError("risk fractions must be in (0, 1]")
        if self.maximum_position_fraction > self.maximum_deployed_fraction:
            raise ValueError("maximum position cannot exceed maximum deployed capital")
        if min(self.maximum_open_positions, self.maximum_trades_per_day) < 1:
            raise ValueError("position and trade limits must be positive")


@dataclass(frozen=True)
class ControlCenterProfile:
    name: str = "Regime-Adaptive Paper"
    paper_capital: float = 100_000.0
    enabled_strategies: tuple[str, ...] = ("intraday_momentum",)
    symbols: tuple[str, ...] = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")
    minimum_candidate_score: float = 0.55
    max_ranked_candidates: int = 20
    paper_only: bool = True
    risk: RiskLimits = field(default_factory=RiskLimits)

    def __post_init__(self) -> None:
        if self.paper_capital <= 0:
            raise ValueError("paper capital must be positive")
        if not self.paper_only:
            raise ValueError("Phase 6.5 profiles must remain paper-only")
        if not 0 <= self.minimum_candidate_score <= 1:
            raise ValueError("minimum candidate score must be between zero and one")
        if self.max_ranked_candidates < 1:
            raise ValueError("max ranked candidates must be positive")


class ProfileStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, profile: ControlCenterProfile) -> Path:
        path = self.directory / f"{_slug(profile.name)}.json"
        payload = asdict(profile)
        payload["enabled_strategies"] = list(profile.enabled_strategies)
        payload["symbols"] = list(profile.symbols)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, name: str) -> ControlCenterProfile:
        path = self.directory / f"{_slug(name)}.json"
        raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        risk = RiskLimits(**cast(dict[str, Any], raw.pop("risk")))
        raw["enabled_strategies"] = tuple(cast(list[str], raw["enabled_strategies"]))
        raw["symbols"] = tuple(cast(list[str], raw["symbols"]))
        return ControlCenterProfile(**raw, risk=risk)

    def list_profiles(self) -> tuple[str, ...]:
        return tuple(path.stem for path in sorted(self.directory.glob("*.json")))


def _slug(value: str) -> str:
    return "_".join(part.lower() for part in value.strip().split() if part)
