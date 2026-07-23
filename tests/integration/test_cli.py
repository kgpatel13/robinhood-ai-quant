from src.main import build_parser, run


def test_healthcheck_cli() -> None:
    assert run(build_parser().parse_args(["healthcheck"])) == 0


def test_config_validation_cli() -> None:
    assert run(build_parser().parse_args(["config-validate"])) == 0
