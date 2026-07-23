from pathlib import Path

from src.common.config import load_yaml, validate_all_configs


def test_load_assets_config() -> None:
    payload = load_yaml(Path("config/assets.yaml"))
    assert payload["version"] == 1
    assert "stock_etf_universe" in payload
    assert "crypto_universe" in payload


def test_validate_all_configs() -> None:
    configs = validate_all_configs(Path("config"))
    assert len(configs) == 8
    assert configs["risk_limits.yaml"]["global"]["live_trading_enabled"] is False
    assert configs["data_sources.yaml"]["storage"]["format"] == "parquet"
