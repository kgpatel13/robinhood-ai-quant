from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from src.common.exceptions import ConfigurationError

REQUIRED_CONFIG_FILES = (
    "assets.yaml",
    "stock_strategy.yaml",
    "crypto_strategy.yaml",
    "risk_limits.yaml",
    "environments.yaml",
    "data_sources.yaml",
)

@dataclass(frozen=True)
class AppSettings:
    app_env: str
    log_level: str
    config_dir: Path
    data_dir: Path
    reports_dir: Path
    logs_dir: Path
    http_timeout_seconds: int
    http_max_retries: int


def load_settings() -> AppSettings:
    load_dotenv()
    return AppSettings(
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        config_dir=Path(os.getenv("CONFIG_DIR", "config")),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        reports_dir=Path(os.getenv("REPORTS_DIR", "reports")),
        logs_dir=Path(os.getenv("LOGS_DIR", "logs")),
        http_timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
        http_max_retries=int(os.getenv("HTTP_MAX_RETRIES", "3")),
    )


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Missing configuration file: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    if payload.get("version") != 1:
        raise ConfigurationError(f"Unsupported or missing version in {path}")
    return payload


def validate_all_configs(config_dir: Path) -> dict[str, dict[str, Any]]:
    loaded = {name: load_yaml(config_dir / name) for name in REQUIRED_CONFIG_FILES}
    risk_global = loaded["risk_limits.yaml"].get("global")
    if not isinstance(risk_global, dict):
        raise ConfigurationError("risk_limits.yaml requires a global mapping")
    prohibited = (
        "live_trading_enabled", "leverage_allowed", "margin_allowed",
        "short_selling_allowed", "options_allowed",
    )
    for key in prohibited:
        if risk_global.get(key) is not False:
            raise ConfigurationError(f"Phase 2 requires {key}: false")
    production = loaded["environments.yaml"].get("production")
    if not isinstance(production, dict) or production.get("allow_live_orders") is not False:
        raise ConfigurationError("Phase 2 requires production allow_live_orders: false")
    storage = loaded["data_sources.yaml"].get("storage")
    if not isinstance(storage, dict) or storage.get("format") != "parquet":
        raise ConfigurationError("Phase 2 requires Parquet storage")
    return loaded
