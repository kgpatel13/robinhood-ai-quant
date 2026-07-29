from pathlib import Path

import pytest

from src.production_platform import (
    CredentialReference,
    DeploymentPolicy,
    DeploymentStage,
    EnvironmentCredentialManager,
    HealthStatus,
    KillSwitch,
    ProductionController,
    RecoveryCheckpoint,
    RecoveryStore,
    ServiceHealth,
)


def healthy_services() -> list[ServiceHealth]:
    return [
        ServiceHealth("broker", HealthStatus.HEALTHY),
        ServiceHealth("market_data", HealthStatus.HEALTHY),
        ServiceHealth("risk", HealthStatus.HEALTHY),
    ]


def test_credentials_resolve_from_environment_reference() -> None:
    manager = EnvironmentCredentialManager({"KEY": "abc", "SECRET": "xyz"})
    credentials = manager.resolve(CredentialReference("broker", "KEY", "SECRET", "paper"))
    assert credentials.api_key == "abc"
    assert credentials.api_secret == "xyz"


def test_missing_credentials_fail_closed() -> None:
    manager = EnvironmentCredentialManager({})
    with pytest.raises(RuntimeError):
        manager.resolve(CredentialReference("broker", "KEY", "SECRET", "live"))


def test_canary_stage_limits_capital() -> None:
    controller = ProductionController(
        DeploymentPolicy(stage=DeploymentStage.CANARY, maximum_canary_capital_fraction=0.02)
    )
    snapshot = controller.evaluate(healthy_services(), reconciliation_clear=True)
    assert snapshot.can_trade
    assert snapshot.capital_fraction == 0.02


def test_production_stage_allows_full_fraction() -> None:
    controller = ProductionController(DeploymentPolicy(stage=DeploymentStage.PRODUCTION))
    snapshot = controller.evaluate(healthy_services(), reconciliation_clear=True)
    assert snapshot.can_trade
    assert snapshot.capital_fraction == 1.0


def test_missing_service_blocks_trading() -> None:
    controller = ProductionController(DeploymentPolicy(stage=DeploymentStage.CANARY))
    snapshot = controller.evaluate([], reconciliation_clear=True)
    assert not snapshot.can_trade
    assert snapshot.capital_fraction == 0.0


def test_reconciliation_failure_blocks_trading() -> None:
    controller = ProductionController(DeploymentPolicy(stage=DeploymentStage.CANARY))
    snapshot = controller.evaluate(healthy_services(), reconciliation_clear=False)
    assert not snapshot.can_trade


def test_kill_switch_blocks_and_can_be_reset() -> None:
    switch = KillSwitch()
    controller = ProductionController(
        DeploymentPolicy(stage=DeploymentStage.CANARY), kill_switch=switch
    )
    switch.engage("operator request", "admin")
    assert not controller.evaluate(healthy_services(), reconciliation_clear=True).can_trade
    switch.reset("admin")
    assert controller.evaluate(healthy_services(), reconciliation_clear=True).can_trade


def test_recovery_store_round_trip(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "checkpoint.json")
    checkpoint = RecoveryCheckpoint(3, ("order-1",), ("AAPL",), {"mode": "canary"})
    store.save(checkpoint)
    assert store.load() == checkpoint


def test_recovery_store_returns_none_when_absent(tmp_path: Path) -> None:
    assert RecoveryStore(tmp_path / "missing.json").load() is None
