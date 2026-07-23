from src.main import run


def test_healthcheck_cli() -> None:
    assert run("healthcheck") == 0


def test_config_validation_cli() -> None:
    assert run("config-validate") == 0
