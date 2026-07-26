from __future__ import annotations

import csv
import json
import math
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.atlas.features import FEATURE_SET_VERSION, build_default_registry
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
from src.atlas.market_models import MarketFeatures, MarketIntelligenceResult, PriceBar
from src.atlas.models import AtlasConfig
from src.atlas.regime import classify_market_regime
from src.atlas.universe import UniverseAsset, load_registry

PLATFORM_VERSION = "2.5.0"
_REQUIRED_BAR_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_price_bars(path: Path) -> list[PriceBar]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or [])
        missing = _REQUIRED_BAR_COLUMNS - columns
        if missing:
            raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
        bars: list[PriceBar] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                bar = PriceBar(
                    timestamp=row["timestamp"].strip(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid OHLCV row at {path}:{line_number}: {exc}") from exc
            if not bar.timestamp:
                raise ValueError(f"Blank timestamp at {path}:{line_number}")
            if min(bar.open, bar.high, bar.low, bar.close) <= 0.0 or bar.volume < 0.0:
                raise ValueError(f"Invalid price or volume at {path}:{line_number}")
            if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(
                bar.open, bar.close, bar.high
            ):
                raise ValueError(f"Inconsistent OHLC values at {path}:{line_number}")
            bars.append(bar)
    bars.sort(key=lambda item: item.timestamp)
    return bars


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _liquidity_score(bars: Sequence[PriceBar]) -> float:
    if not bars:
        return 0.0
    selected = bars[-20:]
    average_dollar_volume = sum(item.close * item.volume for item in selected) / len(selected)
    if average_dollar_volume <= 0.0:
        return 0.0
    return _clamp((math.log10(average_dollar_volume) - 4.0) * 20.0)


def _data_quality_score(bars: Sequence[PriceBar]) -> tuple[float, tuple[str, ...]]:
    warnings: list[str] = []
    score = 100.0
    if len(bars) < 50:
        score -= 35.0
        warnings.append("fewer_than_50_bars")
    elif len(bars) < 100:
        score -= 15.0
        warnings.append("fewer_than_100_bars")
    duplicate_timestamps = len(bars) - len({item.timestamp for item in bars})
    if duplicate_timestamps:
        score -= min(30.0, duplicate_timestamps * 5.0)
        warnings.append("duplicate_timestamps")
    zero_volume_ratio = sum(item.volume == 0.0 for item in bars) / len(bars)
    if zero_volume_ratio > 0.10:
        score -= 20.0
        warnings.append("high_zero_volume_ratio")
    return _clamp(score), tuple(warnings)


def compute_market_features(asset: UniverseAsset, bars: Sequence[PriceBar]) -> MarketFeatures:
    if not bars:
        raise ValueError(f"No price bars supplied for {asset.asset_id}")
    closes = [item.close for item in bars]
    volumes = [item.volume for item in bars]
    sma_20 = simple_moving_average(closes, 20)
    sma_50 = simple_moving_average(closes, 50)
    ema_20 = exponential_moving_average(closes, 20)
    return_20d = percentage_return(closes, 20)
    volatility_20d = annualized_volatility(closes, 20)
    rsi_14 = relative_strength_index(closes, 14)
    close = closes[-1]
    trend_strength = None
    if sma_20 is not None and sma_50 is not None and sma_50 != 0.0:
        trend_strength = (sma_20 - sma_50) / sma_50
    liquidity_score = _liquidity_score(bars)
    data_quality_score, warnings = _data_quality_score(bars)
    volatility_component = 50.0
    if volatility_20d is not None:
        volatility_component = _clamp(100.0 - abs(volatility_20d - 0.25) * 125.0)
    trend_component = 50.0
    if trend_strength is not None:
        trend_component = _clamp(50.0 + trend_strength * 500.0)
    market_quality_score = _clamp(
        0.40 * liquidity_score
        + 0.30 * data_quality_score
        + 0.15 * volatility_component
        + 0.15 * trend_component
    )
    regime = classify_market_regime(
        return_20d=return_20d,
        volatility_20d=volatility_20d,
        close=close,
        sma_20=sma_20,
        sma_50=sma_50,
        rsi_14=rsi_14,
    )
    return MarketFeatures(
        asset_id=asset.asset_id,
        symbol=asset.symbol,
        asset_class=asset.asset_class,
        timestamp=bars[-1].timestamp,
        close=close,
        return_1d=percentage_return(closes, 1),
        return_5d=percentage_return(closes, 5),
        return_20d=return_20d,
        volatility_20d=volatility_20d,
        sma_20=sma_20,
        sma_50=sma_50,
        ema_20=ema_20,
        atr_14=average_true_range(bars, 14),
        rsi_14=rsi_14,
        relative_volume_20d=relative_volume(volumes, 20),
        distance_from_20d_high=distance_from_high(closes, 20),
        trend_strength=trend_strength,
        liquidity_score=liquidity_score,
        data_quality_score=data_quality_score,
        market_quality_score=market_quality_score,
        regime=regime,
        warnings=warnings,
        extended_features=build_default_registry().compute(bars),
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    temporary.replace(path)


def _write_feature_csv(path: Path, features: Sequence[MarketFeatures]) -> None:
    fieldnames = [
        name for name in MarketFeatures.__dataclass_fields__ if name != "extended_features"
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for feature in features:
            row = asdict(feature)
            row.pop("extended_features", None)
            row["warnings"] = "|".join(feature.warnings)
            writer.writerow(row)
        temporary = Path(stream.name)
    temporary.replace(path)


def _write_extended_feature_csv(path: Path, features: Sequence[MarketFeatures]) -> None:
    registry = build_default_registry()
    feature_names = [item.metadata.name for item in registry.definitions()]
    fieldnames = ["asset_id", "symbol", "asset_class", "timestamp", *feature_names]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for feature in features:
            row: dict[str, Any] = {
                "asset_id": feature.asset_id,
                "symbol": feature.symbol,
                "asset_class": feature.asset_class,
                "timestamp": feature.timestamp,
            }
            row.update(feature.extended_features)
            writer.writerow(row)
        temporary = Path(stream.name)
    temporary.replace(path)


def _feature_statistics(
    features: Sequence[MarketFeatures],
) -> dict[str, dict[str, float | int | None]]:
    registry = build_default_registry()
    output: dict[str, dict[str, float | int | None]] = {}
    for definition in registry.definitions():
        name = definition.metadata.name
        values = [
            item.extended_features[name]
            for item in features
            if item.extended_features.get(name) is not None
        ]
        numeric = [float(value) for value in values if value is not None]
        output[name] = {
            "count": len(numeric),
            "coverage": len(numeric) / len(features) if features else 0.0,
            "minimum": min(numeric) if numeric else None,
            "maximum": max(numeric) if numeric else None,
            "mean": sum(numeric) / len(numeric) if numeric else None,
        }
    return output


def _history_path(root: Path, asset: UniverseAsset) -> Path:
    safe_id = asset.asset_id.replace(":", "__").replace("/", "_")
    return root / f"{safe_id}.csv"


def run_market_intelligence(config: AtlasConfig) -> MarketIntelligenceResult:
    generated_at = _utc_now()
    registry = [asset for asset in load_registry(config.universe_registry_path) if asset.active]
    features: list[MarketFeatures] = []
    errors: dict[str, str] = {}
    for asset in registry:
        history_path = _history_path(config.market_history_root, asset)
        if not history_path.exists():
            continue
        try:
            features.append(compute_market_features(asset, load_price_bars(history_path)))
        except ValueError as exc:
            errors[asset.asset_id] = str(exc)

    features.sort(key=lambda item: (-item.market_quality_score, item.asset_id))
    _write_feature_csv(config.market_feature_store_path, features)
    _write_extended_feature_csv(config.feature_intelligence_store_path, features)
    feature_registry = build_default_registry()
    _atomic_write(
        config.feature_dictionary_path,
        json.dumps(
            {
                "platform_version": PLATFORM_VERSION,
                "feature_set_version": FEATURE_SET_VERSION,
                "feature_count": len(feature_registry.definitions()),
                "features": feature_registry.metadata_payload(),
            },
            indent=2,
            sort_keys=True,
        ),
    )
    _atomic_write(
        config.feature_statistics_path,
        json.dumps(
            {
                "platform_version": PLATFORM_VERSION,
                "feature_set_version": FEATURE_SET_VERSION,
                "asset_count": len(features),
                "statistics": _feature_statistics(features),
            },
            indent=2,
            sort_keys=True,
        ),
    )
    snapshot_payload: dict[str, Any] = {
        "platform_version": PLATFORM_VERSION,
        "generated_at_utc": generated_at,
        "feature_set_version": FEATURE_SET_VERSION,
        "extended_feature_count": len(feature_registry.definitions()),
        "features": [asdict(item) for item in features],
    }
    _atomic_write(
        config.market_snapshot_path,
        json.dumps(snapshot_payload, indent=2, sort_keys=True),
    )
    regime_counts: dict[str, int] = {}
    for feature in features:
        regime_counts[feature.regime] = regime_counts.get(feature.regime, 0) + 1
    result = MarketIntelligenceResult(
        platform_version=PLATFORM_VERSION,
        generated_at_utc=generated_at,
        registry_assets=len(registry),
        processed_assets=len(features),
        skipped_assets=len(registry) - len(features),
        regime_counts=regime_counts,
        feature_store_path=str(config.market_feature_store_path),
        market_snapshot_path=str(config.market_snapshot_path),
        errors=errors,
        complete=not errors,
    )
    _atomic_write(
        config.market_report_path,
        json.dumps(asdict(result), indent=2, sort_keys=True),
    )
    return result
