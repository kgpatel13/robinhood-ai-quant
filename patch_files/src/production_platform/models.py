from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class DeploymentStage(StrEnum):
    OFFLINE = "offline"
    PAPER = "paper"
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"
    HALTED = "halted"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class CredentialReference:
    provider: str
    key_name: str
    secret_name: str
    environment: str

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.key_name.strip() or not self.secret_name.strip():
            raise ValueError("credential references must be non-empty")


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    service: str
    status: HealthStatus
    message: str = ""


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    engaged: bool
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True, slots=True)
class DeploymentPolicy:
    stage: DeploymentStage = DeploymentStage.OFFLINE
    maximum_canary_capital_fraction: float = 0.01
    require_reconciliation: bool = True
    require_healthy_services: bool = True
    required_services: frozenset[str] = frozenset({"broker", "market_data", "risk"})

    def __post_init__(self) -> None:
        if not 0.0 <= self.maximum_canary_capital_fraction <= 1.0:
            raise ValueError("maximum_canary_capital_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ProductionSnapshot:
    stage: DeploymentStage
    can_trade: bool
    capital_fraction: float
    kill_switch: KillSwitchState
    service_health: Mapping[str, ServiceHealth] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
