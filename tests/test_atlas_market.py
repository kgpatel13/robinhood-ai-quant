from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.atlas.indicators import (
    annualized_volatility,
    average_true_range,
    distance_from_high,
    exponential_moving_average,
    percentage_return,
    relative_strength_index,
    relative_volume,
    simple_moving_average,
)
from src.atlas.market import compute_market_features, load_price_bars, run_market_intelligence
from src.atlas.market_models import PriceBar
from src.atlas.models import AtlasConfig
from src.atlas.regime import classify_market_regime
from src.atlas.universe import UniverseAsset, write_registry


def _bars(count: int = 80, *, start: float = 100.0, step: float = 1.0) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for index in range(count):
        close = start + index * step
        bars.append(
            PriceBar(
                timestamp=f"2026-01-{index + 1:03d}",
                open=close - 0.25,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000.0 + index * 10_000.0,
            )
        )
    return bars


def _asset() -> UniverseAsset:
    return UniverseAsset(
        asset_id="stock:TEST",
        symbol="TEST",
        name="Test Corp",
        asset_class="stock",
        exchange="NASDAQ",
        source="test",
        source_id="TEST",
        active=True,
        tradable=True,
        is_etf=False,
    )


def _write_bars(path: Path, bars: list[PriceBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(PriceBar.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(item) for item in bars)


def test_indicator_values() -> None:
    values = [float(item) for item in range(1, 31)]
    assert simple_moving_average(values, 5) == pytest.approx(28.0)
    assert exponential_moving_average(values, 5) is not None
    assert percentage_return(values, 5) == pytest.approx(30.0 / 25.0 - 1.0)
    assert annualized_volatility(values, 20) is not None
    assert relative_strength_index(values, 14) == 100.0
    assert relative_volume([100.0] * 20 + [200.0], 20) == 2.0
    assert distance_from_high(values, 20) == 0.0
    assert average_true_range(_bars(20), 14) == pytest.approx(2.0)


def test_indicator_validation() -> None:
    with pytest.raises(ValueError):
        simple_moving_average([1.0], 0)
    with pytest.raises(ValueError):
        percentage_return([1.0], 0)


def test_regime_classification() -> None:
    assert classify_market_regime(
        return_20d=0.12,
        volatility_20d=0.20,
        close=120.0,
        sma_20=115.0,
        sma_50=105.0,
        rsi_14=70.0,
    ) == "strong_bull"
    assert classify_market_regime(
        return_20d=-0.25,
        volatility_20d=0.60,
        close=70.0,
        sma_20=80.0,
        sma_50=90.0,
        rsi_14=20.0,
    ) == "crash"
    assert classify_market_regime(
        return_20d=None,
        volatility_20d=None,
        close=100.0,
        sma_20=None,
        sma_50=None,
        rsi_14=None,
    ) == "insufficient_data"


def test_load_price_bars_and_feature_computation(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    _write_bars(path, _bars())
    bars = load_price_bars(path)
    features = compute_market_features(_asset(), bars)
    assert len(bars) == 80
    assert features.symbol == "TEST"
    assert features.regime == "strong_bull"
    assert features.market_quality_score > 0.0
    assert features.data_quality_score == 85.0
    assert features.rsi_14 == 100.0


def test_load_price_bars_rejects_invalid_ohlc(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n2026-01-01,10,9,8,10,100\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Inconsistent OHLC"):
        load_price_bars(path)


def test_market_intelligence_pipeline(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    feature_path = tmp_path / "features.csv"
    snapshot_path = tmp_path / "market_snapshot.json"
    report_path = tmp_path / "market_report.json"
    history_root = tmp_path / "daily"
    write_registry(registry_path, [_asset()])
    _write_bars(history_root / "stock__TEST.csv", _bars(120))
    config = AtlasConfig(
        universe_registry_path=registry_path,
        market_history_root=history_root,
        market_feature_store_path=feature_path,
        market_snapshot_path=snapshot_path,
        market_report_path=report_path,
    )

    result = run_market_intelligence(config)

    assert result.complete is True
    assert result.registry_assets == 1
    assert result.processed_assets == 1
    assert result.skipped_assets == 0
    assert feature_path.exists()
    assert snapshot_path.exists()
    assert report_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["platform_version"] == "2.2.0"
    assert snapshot["features"][0]["asset_id"] == "stock:TEST"
