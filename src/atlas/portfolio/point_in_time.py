from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.atlas.portfolio.core import PortfolioCandidate


@dataclass(frozen=True)
class PointInTimeConfig:
    minimum_history_observations: int = 126
    rebalance_observations: int = 63
    momentum_short: int = 20
    momentum_medium: int = 60
    momentum_long: int = 126
    volatility_window: int = 60
    trend_window: int = 50
    volume_window: int = 20
    maximum_absolute_daily_return: float = 0.50
    minimum_price: float = 3.0
    maximum_assets: int | None = None

    def __post_init__(self) -> None:
        integer_fields = (
            self.minimum_history_observations,
            self.rebalance_observations,
            self.momentum_short,
            self.momentum_medium,
            self.momentum_long,
            self.volatility_window,
            self.trend_window,
            self.volume_window,
        )
        if any(value < 1 for value in integer_fields):
            raise ValueError("point-in-time observation settings must be positive")
        if not 0.0 < self.maximum_absolute_daily_return <= 1.0:
            raise ValueError("maximum_absolute_daily_return must be within (0, 1]")
        if self.minimum_price < 0:
            raise ValueError("minimum_price must be non-negative")
        if self.maximum_assets is not None and self.maximum_assets < 1:
            raise ValueError("maximum_assets must be positive when supplied")


@dataclass(frozen=True)
class SnapshotRecord:
    as_of: str
    path: str
    asset_count: int
    eligible_asset_count: int
    source_asset_count: int
    earliest_source_date: str | None
    latest_source_date: str | None
    sha256: str


@dataclass(frozen=True)
class SnapshotBuildResult:
    snapshots: tuple[SnapshotRecord, ...]
    manifest: dict[str, Any]
    leakage_audit: dict[str, Any]
    coverage: pd.DataFrame


def _asset_id_from_path(path: Path) -> tuple[str, str, str] | None:
    stem = path.stem
    if "__" not in stem:
        return None
    asset_class, symbol = stem.split("__", 1)
    if asset_class not in {"stock", "crypto"} or not symbol:
        return None
    return f"{asset_class}:{symbol}", symbol, asset_class


def _read_metadata(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    frame = pd.read_csv(path)
    if "asset_id" not in frame.columns:
        raise ValueError("metadata must contain asset_id")
    result: dict[str, dict[str, Any]] = {}
    for raw_row in frame.to_dict(orient="records"):
        row: dict[str, Any] = {str(key): value for key, value in raw_row.items()}
        asset_id = str(row.get("asset_id", "")).strip()
        if asset_id:
            result[asset_id] = row
    return result


def _load_history(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"timestamp", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} is missing required columns: {sorted(required)}")
    frame = frame[["timestamp", "close", "volume"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    frame = frame.drop_duplicates(subset=["timestamp"], keep="last")
    return frame.set_index("timestamp")


def _finite(value: object) -> float | None:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _return_over(close: pd.Series, observations: int) -> float | None:
    if len(close) <= observations:
        return None
    first = _finite(close.iloc[-observations - 1])
    last = _finite(close.iloc[-1])
    if first is None or last is None or first <= 0:
        return None
    return last / first - 1.0


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    mean = float(numeric.mean()) if numeric.notna().any() else 0.0
    std = float(numeric.std(ddof=0)) if numeric.notna().sum() > 1 else 0.0
    if not math.isfinite(std) or std <= 1e-12:
        return pd.Series(0.0, index=series.index, dtype=float)
    return (numeric - mean) / std


def _feature_row(
    asset_id: str,
    symbol: str,
    asset_class: str,
    history: pd.DataFrame,
    as_of: pd.Timestamp,
    config: PointInTimeConfig,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    available = history.loc[history.index <= as_of]
    if len(available) < config.minimum_history_observations:
        return None
    close = available["close"].astype(float)
    volume = available["volume"].fillna(0.0).astype(float)
    price = _finite(close.iloc[-1])
    if price is None or price < config.minimum_price:
        return None
    daily = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    daily = daily.where(daily.abs() <= config.maximum_absolute_daily_return).dropna()
    volatility = None
    if len(daily) >= config.volatility_window:
        volatility = float(daily.tail(config.volatility_window).std(ddof=1) * math.sqrt(252.0))
    trend = None
    if len(close) >= config.trend_window:
        average = float(close.tail(config.trend_window).mean())
        trend = price / average - 1.0 if average > 0 else None
    dollar_volume = close * volume
    liquidity_raw = float(dollar_volume.tail(config.volume_window).median())
    expected = max(config.minimum_history_observations, config.momentum_long + 1)
    data_quality = min(len(available) / expected * 100.0, 100.0)
    return {
        "asset_id": asset_id,
        "symbol": str(metadata.get("symbol") or symbol),
        "asset_class": str(metadata.get("asset_class") or asset_class),
        "timestamp": as_of.date().isoformat(),
        "price": price,
        "return_20d": _return_over(close, config.momentum_short),
        "return_60d": _return_over(close, config.momentum_medium),
        "return_126d": _return_over(close, config.momentum_long),
        "volatility_60d": volatility,
        "trend_strength": trend,
        "liquidity_raw": liquidity_raw,
        "data_quality_score": data_quality,
        "history_observations": len(available),
        "first_observation": available.index.min().date().isoformat(),
        "last_observation": available.index.max().date().isoformat(),
        "sector": metadata.get("sector"),
        "industry": metadata.get("industry"),
        "country": metadata.get("country"),
        "market_cap": metadata.get("market_cap"),
    }


def _rank_snapshot(rows: list[dict[str, Any]], maximum_assets: int | None) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["liquidity_score"] = frame["liquidity_raw"].rank(pct=True) * 100.0
    momentum = (
        0.35 * _zscore(frame["return_20d"])
        + 0.40 * _zscore(frame["return_60d"])
        + 0.25 * _zscore(frame["return_126d"])
    )
    frame["alpha_score"] = (
        momentum
        + 0.35 * _zscore(frame["trend_strength"])
        - 0.30 * _zscore(frame["volatility_60d"])
        + 0.15 * _zscore(frame["liquidity_raw"])
        + 0.10 * _zscore(frame["data_quality_score"])
    )
    frame = frame.sort_values(
        ["alpha_score", "data_quality_score", "liquidity_raw", "asset_id"],
        ascending=[False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)
    if len(frame) == 1:
        frame["alpha_percentile"] = 1.0
    else:
        frame["alpha_percentile"] = 1.0 - (frame.index.to_numpy(dtype=float) / (len(frame) - 1))
    frame["confidence"] = np.where(
        frame["alpha_percentile"] >= 0.90,
        "high",
        np.where(frame["alpha_percentile"] >= 0.70, "medium", "low"),
    )
    frame["factor_coverage"] = frame[
        ["return_20d", "return_60d", "return_126d", "volatility_60d", "trend_strength"]
    ].notna().sum(axis=1)
    if maximum_assets is not None:
        frame = frame.head(maximum_assets).copy()
    columns = [
        "rank",
        "asset_id",
        "symbol",
        "asset_class",
        "timestamp",
        "alpha_score",
        "alpha_percentile",
        "confidence",
        "factor_coverage",
        "price",
        "volatility_60d",
        "liquidity_score",
        "data_quality_score",
        "return_20d",
        "return_60d",
        "return_126d",
        "trend_strength",
        "sector",
        "industry",
        "country",
        "market_cap",
        "history_observations",
        "first_observation",
        "last_observation",
    ]
    return frame.reindex(columns=columns)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_dates(
    histories: dict[str, pd.DataFrame],
    config: PointInTimeConfig,
) -> list[pd.Timestamp]:
    if not histories:
        return []
    calendar = sorted({date for frame in histories.values() for date in frame.index})
    if len(calendar) < config.minimum_history_observations:
        return []
    first = config.minimum_history_observations - 1
    return calendar[first:: config.rebalance_observations]


def build_point_in_time_snapshots(
    history_directory: Path,
    output_directory: Path,
    metadata_path: Path | None = None,
    config: PointInTimeConfig | None = None,
) -> SnapshotBuildResult:
    cfg = config or PointInTimeConfig()
    metadata = _read_metadata(metadata_path)
    histories: dict[str, pd.DataFrame] = {}
    identities: dict[str, tuple[str, str]] = {}
    rejected: dict[str, str] = {}
    for path in sorted(history_directory.glob("*.csv")):
        identity = _asset_id_from_path(path)
        if identity is None:
            continue
        asset_id, symbol, asset_class = identity
        try:
            history = _load_history(path)
        except (OSError, ValueError) as exc:
            rejected[asset_id] = str(exc)
            continue
        if history.empty:
            rejected[asset_id] = "empty_history"
            continue
        histories[asset_id] = history
        identities[asset_id] = (symbol, asset_class)
    dates = _snapshot_dates(histories, cfg)
    if not dates:
        raise ValueError("No point-in-time snapshot dates could be produced")
    output_directory.mkdir(parents=True, exist_ok=True)
    snapshot_directory = output_directory / "snapshots"
    snapshot_directory.mkdir(parents=True, exist_ok=True)
    records: list[SnapshotRecord] = []
    coverage_rows: list[dict[str, Any]] = []
    leakage_violations: list[dict[str, str]] = []
    for as_of in dates:
        rows: list[dict[str, Any]] = []
        for asset_id, history in histories.items():
            symbol, asset_class = identities[asset_id]
            row = _feature_row(
                asset_id,
                symbol,
                asset_class,
                history,
                as_of,
                cfg,
                metadata.get(asset_id, {}),
            )
            if row is not None:
                rows.append(row)
        ranked = _rank_snapshot(rows, cfg.maximum_assets)
        if ranked.empty:
            continue
        future_rows = ranked[pd.to_datetime(ranked["last_observation"]) > as_of]
        if not future_rows.empty:
            leakage_violations.extend(
                {
                    "as_of": as_of.date().isoformat(),
                    "asset_id": str(asset_id),
                    "last_observation": str(last_observation),
                }
                for asset_id, last_observation in zip(
                    future_rows["asset_id"], future_rows["last_observation"], strict=True
                )
            )
        path = snapshot_directory / f"ranked_assets_{as_of.date().isoformat()}.csv"
        ranked.to_csv(path, index=False)
        eligible = int((ranked["alpha_percentile"] >= 0.70).sum())
        records.append(
            SnapshotRecord(
                as_of=as_of.date().isoformat(),
                path=str(path),
                asset_count=len(ranked),
                eligible_asset_count=eligible,
                source_asset_count=len(histories),
                earliest_source_date=min(
                    (frame.index.min().date().isoformat() for frame in histories.values()),
                    default=None,
                ),
                latest_source_date=max(
                    (frame.index.max().date().isoformat() for frame in histories.values()),
                    default=None,
                ),
                sha256=_sha256(path),
            )
        )
        coverage_rows.append(
            {
                "as_of": as_of.date().isoformat(),
                "ranked_assets": len(ranked),
                "eligible_assets": eligible,
                "stock_assets": int((ranked["asset_class"] == "stock").sum()),
                "crypto_assets": int((ranked["asset_class"] == "crypto").sum()),
                "median_history_observations": float(ranked["history_observations"].median()),
                "metadata_coverage": float(ranked["sector"].notna().mean()),
            }
        )
    if not records:
        raise ValueError("Historical data produced no usable ranked snapshots")
    manifest: dict[str, Any] = {
        "phase": "4.6",
        "paper_only": True,
        "snapshot_count": len(records),
        "source_asset_count": len(histories),
        "rejected_asset_count": len(rejected),
        "first_snapshot": records[0].as_of,
        "last_snapshot": records[-1].as_of,
        "configuration": asdict(cfg),
        "feature_provenance": {
            "price_and_volume": "point_in_time_daily_history_cutoff_at_as_of",
            "technical_features": "point_in_time_computed_from_rows_at_or_before_as_of",
            "sector_industry_country": "static_current_metadata_not_historically_versioned",
            "market_cap": "static_current_metadata_not_historically_versioned",
            "fundamentals": "not_used",
        },
        "snapshots": [asdict(record) for record in records],
        "rejected_assets": rejected,
    }
    leakage_audit = {
        "passed": not leakage_violations,
        "violation_count": len(leakage_violations),
        "violations": leakage_violations,
        "rule": "last_observation_must_be_less_than_or_equal_to_snapshot_as_of",
        "static_metadata_warning": (
            "sector, industry, country, and market_cap come from current metadata and are "
            "not certified point-in-time"
        ),
    }
    coverage = pd.DataFrame(coverage_rows)
    (output_directory / "snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_directory / "leakage_audit.json").write_text(
        json.dumps(leakage_audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    coverage.to_csv(output_directory / "snapshot_coverage.csv", index=False)
    return SnapshotBuildResult(
        snapshots=tuple(records),
        manifest=manifest,
        leakage_audit=leakage_audit,
        coverage=coverage,
    )


def load_snapshot_candidates(snapshot_path: Path) -> list[PortfolioCandidate]:
    frame = pd.read_csv(snapshot_path)
    required = {
        "rank",
        "asset_id",
        "symbol",
        "asset_class",
        "alpha_score",
        "alpha_percentile",
        "confidence",
    }
    if not required.issubset(frame.columns):
        raise ValueError(f"snapshot is missing required columns: {sorted(required)}")
    candidates: list[PortfolioCandidate] = []
    for row in frame.to_dict(orient="records"):
        candidates.append(
            PortfolioCandidate(
                rank=int(row["rank"]),
                asset_id=str(row["asset_id"]),
                symbol=str(row["symbol"]),
                asset_class=str(row["asset_class"]),
                alpha_score=float(row["alpha_score"]),
                alpha_percentile=float(row["alpha_percentile"]),
                confidence=str(row["confidence"]),
                volatility_60d=_finite(row.get("volatility_60d")),
                price=_finite(row.get("price")),
                sector=str(row["sector"]) if pd.notna(row.get("sector")) else None,
                industry=str(row["industry"]) if pd.notna(row.get("industry")) else None,
                country=str(row["country"]) if pd.notna(row.get("country")) else None,
                market_cap=_finite(row.get("market_cap")),
                liquidity_score=_finite(row.get("liquidity_score")),
                data_quality_score=_finite(row.get("data_quality_score")),
            )
        )
    return candidates


def resolve_snapshot(snapshot_directory: Path, as_of: str | pd.Timestamp) -> Path:
    target = pd.Timestamp(as_of)
    matches: list[tuple[pd.Timestamp, Path]] = []
    for path in snapshot_directory.glob("ranked_assets_*.csv"):
        text = path.stem.removeprefix("ranked_assets_")
        try:
            date = pd.Timestamp(text)
        except ValueError:
            continue
        if date <= target:
            matches.append((date, path))
    if not matches:
        raise FileNotFoundError(f"No snapshot exists at or before {target.date().isoformat()}")
    return max(matches, key=lambda item: item[0])[1]
