from pathlib import Path

from src.common.config import AppSettings
from src.common.health import collect_health


def test_health_disables_live_trading() -> None:
    settings = AppSettings(
        app_env="test",
        log_level="INFO",
        config_dir=Path("config"),
        data_dir=Path("data"),
        reports_dir=Path("reports"),
        logs_dir=Path("logs"),
    )
    result = collect_health(settings)
    assert result["live_trading_capability"] is False
