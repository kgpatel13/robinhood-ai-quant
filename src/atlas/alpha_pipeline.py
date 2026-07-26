from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.atlas.factors import (
    CompositeAlphaConfig,
    FactorEngine,
    FactorEngineConfig,
    build_default_registry,
    compute_composite_alpha,
    factor_correlations,
    factor_statistics,
)
from src.atlas.ranking import RankedAsset, RankingConfig, RankingEngine
from src.atlas.version import __version__


@dataclass(frozen=True)
class AlphaPipelineConfig:
    feature_store_path: Path = Path("data/market/features_v2.csv")
    report_directory: Path = Path("reports/atlas_v3")
    top_n: int = 25
    bottom_n: int = 10


@dataclass(frozen=True)
class AlphaPipelineResult:
    complete: bool
    platform_version: str
    generated_at_utc: str
    input_assets: int
    ranked_assets: int
    excluded_assets: int
    report_directory: str
    artifacts: dict[str, str]
    errors: dict[str, str]


def _number(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except ValueError:
        return None
    return numeric if math.isfinite(numeric) else None


def _read_feature_store(
    path: Path,
) -> tuple[dict[str, dict[str, float | None]], dict[str, dict[str, str]]]:
    features: dict[str, dict[str, float | None]] = {}
    metadata: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"asset_id", "symbol", "asset_class", "timestamp"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Feature store is missing required columns: {sorted(required)}")
        for row in reader:
            asset_id = row["asset_id"]
            if not asset_id:
                continue
            metadata[asset_id] = {
                "symbol": row.get("symbol", asset_id),
                "asset_class": row.get("asset_class", "unknown"),
                "timestamp": row.get("timestamp", ""),
            }
            features[asset_id] = {
                key: _number(value) for key, value in row.items() if key not in required
            }
    return features, metadata


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_factor_scores(
    path: Path,
    metadata: dict[str, dict[str, str]],
    raw_scores: dict[str, dict[str, float | None]],
    normalized_scores: dict[str, dict[str, float | None]],
    coverage: dict[str, dict[str, int]],
) -> None:
    factors = sorted({name for row in normalized_scores.values() for name in row})
    columns = ["asset_id", "symbol", "asset_class", "timestamp"]
    columns += [f"{name}_raw" for name in factors]
    columns += [f"{name}_score" for name in factors]
    columns += [f"{name}_components" for name in factors]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for asset_id in sorted(normalized_scores):
            row: dict[str, object] = {"asset_id": asset_id, **metadata.get(asset_id, {})}
            for factor in factors:
                row[f"{factor}_raw"] = raw_scores[asset_id].get(factor)
                row[f"{factor}_score"] = normalized_scores[asset_id].get(factor)
                row[f"{factor}_components"] = coverage[asset_id].get(factor, 0)
            writer.writerow(row)


def _write_rankings(path: Path, ranked_assets: tuple[RankedAsset, ...]) -> None:
    factors = sorted({name for asset in ranked_assets for name in asset.factor_scores})
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
        *factors,
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for asset in ranked_assets:
            row = {
                "rank": asset.rank,
                "asset_id": asset.asset_id,
                "symbol": asset.symbol,
                "asset_class": asset.asset_class,
                "timestamp": asset.timestamp,
                "alpha_score": asset.alpha_score,
                "alpha_percentile": asset.alpha_percentile,
                "confidence": asset.confidence,
                "factor_coverage": asset.factor_coverage,
                **asset.factor_scores,
            }
            writer.writerow(row)


def run_alpha_pipeline(config: AlphaPipelineConfig | None = None) -> AlphaPipelineResult:
    selected = config or AlphaPipelineConfig()
    generated_at = datetime.now(UTC).isoformat()
    artifacts: dict[str, str] = {}
    errors: dict[str, str] = {}
    input_assets = 0
    ranked_count = 0
    excluded_count = 0
    try:
        features, metadata = _read_feature_store(selected.feature_store_path)
        input_assets = len(features)
        selected.report_directory.mkdir(parents=True, exist_ok=True)

        registry = build_default_registry()
        factor_result = FactorEngine(registry, FactorEngineConfig()).compute(features)
        alpha_scores = compute_composite_alpha(
            factor_result.normalized_scores,
            CompositeAlphaConfig(),
        )
        ranking = RankingEngine(
            RankingConfig(top_n=selected.top_n, bottom_n=selected.bottom_n)
        ).rank(alpha_scores, factor_result.normalized_scores, metadata)
        ranked_count = len(ranking.ranked_assets)
        excluded_count = len(ranking.excluded_assets)

        factor_scores_path = selected.report_directory / "factor_scores.csv"
        ranked_assets_path = selected.report_directory / "ranked_assets.csv"
        factor_statistics_path = selected.report_directory / "factor_statistics.json"
        factor_correlations_path = selected.report_directory / "factor_correlations.json"
        top_opportunities_path = selected.report_directory / "top_opportunities.json"
        ranking_summary_path = selected.report_directory / "ranking_summary.json"
        factor_dictionary_path = selected.report_directory / "factor_dictionary.json"

        _write_factor_scores(
            factor_scores_path,
            metadata,
            factor_result.raw_scores,
            factor_result.normalized_scores,
            factor_result.component_coverage,
        )
        _write_rankings(ranked_assets_path, ranking.ranked_assets)
        _write_json(
            factor_statistics_path,
            {
                name: asdict(statistic)
                for name, statistic in factor_statistics(factor_result.normalized_scores).items()
            },
        )
        _write_json(
            factor_correlations_path,
            factor_correlations(factor_result.normalized_scores),
        )
        _write_json(factor_dictionary_path, registry.metadata_payload())
        _write_json(
            top_opportunities_path,
            {
                "platform_version": __version__,
                "generated_at_utc": generated_at,
                "top": [asdict(asset) for asset in ranking.top_assets],
                "bottom": [asdict(asset) for asset in ranking.bottom_assets],
            },
        )
        _write_json(
            ranking_summary_path,
            {
                "complete": True,
                "platform_version": __version__,
                "generated_at_utc": generated_at,
                "input_assets": input_assets,
                "ranked_assets": ranked_count,
                "excluded_assets": excluded_count,
                "factor_count": len(registry.definitions()),
                "top_n": selected.top_n,
                "bottom_n": selected.bottom_n,
                "alpha_weights": dict(CompositeAlphaConfig().weights),
            },
        )
        artifacts = {
            "factor_scores": str(factor_scores_path),
            "ranked_assets": str(ranked_assets_path),
            "factor_statistics": str(factor_statistics_path),
            "factor_correlations": str(factor_correlations_path),
            "factor_dictionary": str(factor_dictionary_path),
            "top_opportunities": str(top_opportunities_path),
            "ranking_summary": str(ranking_summary_path),
        }
    except (OSError, ValueError) as exc:
        errors["pipeline"] = str(exc)

    return AlphaPipelineResult(
        complete=not errors,
        platform_version=__version__,
        generated_at_utc=generated_at,
        input_assets=input_assets,
        ranked_assets=ranked_count,
        excluded_assets=excluded_count,
        report_directory=str(selected.report_directory),
        artifacts=artifacts,
        errors=errors,
    )
