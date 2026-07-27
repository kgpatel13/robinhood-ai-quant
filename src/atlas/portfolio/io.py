from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

from src.atlas.portfolio.core import (
    CurrentPosition,
    PortfolioCandidate,
    PortfolioResult,
    finite_number,
)


class FeatureRecord(TypedDict):
    volatility_60d: float | None
    price: float | None
    sector: str | None
    industry: str | None
    country: str | None
    market_cap: float | None
    liquidity_score: float | None
    data_quality_score: float | None


def _first(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def read_candidates(
    ranked_assets_path: Path,
    feature_store_path: Path | None = None,
    metadata_path: Path | None = None,
) -> list[PortfolioCandidate]:
    features: dict[str, FeatureRecord] = {}
    if feature_store_path and feature_store_path.exists():
        with feature_store_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            for row in csv.DictReader(handle):
                asset_id = row.get("asset_id", "")
                if asset_id:
                    features[asset_id] = {
                        "volatility_60d": finite_number(
                            _first(
                                row,
                                "volatility_60d",
                                "volatility_20d",
                                "realized_volatility_60d",
                                "vol_60d",
                            )
                        ),
                        "price": finite_number(
                            _first(
                                row,
                                "close",
                                "price",
                                "latest_price",
                                "adj_close",
                            )
                        ),
                        "sector": _first(row, "sector", "gics_sector"),
                        "industry": _first(row, "industry", "gics_industry"),
                        "country": _first(row, "country", "domicile"),
                        "market_cap": finite_number(
                            _first(row, "market_cap", "market_capitalization")
                        ),
                        "liquidity_score": finite_number(
                            _first(row, "liquidity_score", "liquidity")
                        ),
                        "data_quality_score": finite_number(
                            _first(row, "data_quality_score", "quality_score")
                        ),
                    }

    if metadata_path and metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                asset_id = row.get("asset_id", "").strip()
                if not asset_id:
                    continue
                current = features.get(asset_id)
                if current is None:
                    current = {
                        "volatility_60d": None,
                        "price": None,
                        "sector": None,
                        "industry": None,
                        "country": None,
                        "market_cap": None,
                        "liquidity_score": None,
                        "data_quality_score": None,
                    }
                features[asset_id] = {
                    **current,
                    "sector": _first(row, "sector", "gics_sector") or current["sector"],
                    "industry": _first(row, "industry", "gics_industry") or current["industry"],
                    "country": _first(row, "country", "domicile") or current["country"],
                    "market_cap": finite_number(
                        _first(row, "market_cap", "market_capitalization")
                    ) or current["market_cap"],
                    "liquidity_score": current["liquidity_score"],
                    "data_quality_score": current["data_quality_score"],
                }

    candidates: list[PortfolioCandidate] = []
    with ranked_assets_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "rank",
            "asset_id",
            "symbol",
            "asset_class",
            "alpha_score",
            "alpha_percentile",
            "confidence",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"Ranked assets are missing required columns: {sorted(required)}"
            )

        for row in reader:
            asset_id = row["asset_id"]
            extra = features.get(asset_id)

            row_volatility = finite_number(
                _first(
                    row,
                    "volatility_60d",
                    "volatility_20d",
                    "realized_volatility_60d",
                    "vol_60d",
                )
            )
            row_price = finite_number(row.get("price"))
            row_sector = _first(row, "sector", "gics_sector")
            row_industry = _first(row, "industry", "gics_industry")
            row_country = _first(row, "country", "domicile")
            row_market_cap = finite_number(row.get("market_cap"))

            candidates.append(
                PortfolioCandidate(
                    rank=int(row["rank"]),
                    asset_id=asset_id,
                    symbol=row["symbol"],
                    asset_class=row["asset_class"],
                    alpha_score=float(row["alpha_score"]),
                    alpha_percentile=float(row["alpha_percentile"]),
                    confidence=row["confidence"],
                    volatility_60d=(
                        row_volatility
                        if row_volatility is not None
                        else extra["volatility_60d"] if extra else None
                    ),
                    price=(
                        row_price
                        if row_price is not None
                        else extra["price"] if extra else None
                    ),
                    sector=(
                        row_sector
                        if row_sector is not None
                        else extra["sector"] if extra else None
                    ),
                    industry=(
                        row_industry
                        if row_industry is not None
                        else extra["industry"] if extra else None
                    ),
                    country=(
                        row_country
                        if row_country is not None
                        else extra["country"] if extra else None
                    ),
                    market_cap=(
                        row_market_cap
                        if row_market_cap is not None
                        else extra["market_cap"] if extra else None
                    ),
                    liquidity_score=(
                        finite_number(row.get("liquidity_score"))
                        if finite_number(row.get("liquidity_score")) is not None
                        else extra["liquidity_score"] if extra else None
                    ),
                    data_quality_score=(
                        finite_number(row.get("data_quality_score"))
                        if finite_number(row.get("data_quality_score")) is not None
                        else extra["data_quality_score"] if extra else None
                    ),
                )
            )
    return candidates


def read_current_positions(path: Path | None) -> list[CurrentPosition]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("positions", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Existing portfolio must be a list or contain a positions list")
    positions: list[CurrentPosition] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each existing position must be an object")
        positions.append(
            CurrentPosition(
                asset_id=str(row["asset_id"]),
                symbol=str(row.get("symbol", row["asset_id"])),
                asset_class=str(row.get("asset_class", "stock")),
                market_value=float(row["market_value"]),
            )
        )
    return positions


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _exposure(targets: tuple[Any, ...], field: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for position in targets:
        value = getattr(position, field, None)
        if value:
            result[str(value)] = result.get(str(value), 0.0) + position.target_weight
    return result


def write_reports(result: PortfolioResult, output_directory: Path) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "portfolio": output_directory / "portfolio.json",
        "portfolio_metrics": output_directory / "portfolio_metrics.json",
        "risk_report": output_directory / "risk_report.json",
        "rebalance_plan": output_directory / "rebalance_plan.json",
        "allocation_summary": output_directory / "allocation_summary.json",
        "orders_preview": output_directory / "orders_preview.json",
        "excluded_assets": output_directory / "excluded_assets.json",
    }
    _write_json(
        paths["portfolio"],
        {"positions": [asdict(item) for item in result.targets]},
    )
    _write_json(
        paths["portfolio_metrics"],
        {**asdict(result.metrics), "diagnostics": asdict(result.diagnostics)},
    )
    exclusion_summary = dict(sorted(Counter(result.excluded.values()).items()))
    _write_json(
        paths["excluded_assets"],
        {"excluded_assets": dict(result.excluded)},
    )
    _write_json(
        paths["risk_report"],
        {
            "largest_position_weight": result.metrics.largest_position_weight,
            "crypto_weight": result.metrics.crypto_weight,
            "concentration_hhi": result.metrics.concentration_hhi,
            "effective_positions": result.metrics.effective_positions,
            "estimated_volatility": result.metrics.estimated_volatility,
            "sector_exposure": _exposure(result.targets, "sector"),
            "industry_exposure": _exposure(result.targets, "industry"),
            "country_exposure": _exposure(result.targets, "country"),
            "diagnostics": asdict(result.diagnostics),
            "exclusion_summary": exclusion_summary,
            "excluded_assets_file": paths["excluded_assets"].name,
        },
    )
    _write_json(
        paths["rebalance_plan"],
        {"actions": [asdict(item) for item in result.actions]},
    )
    by_class: dict[str, float] = {}
    for position in result.targets:
        by_class[position.asset_class] = (
            by_class.get(position.asset_class, 0.0) + position.target_weight
        )
    _write_json(
        paths["allocation_summary"],
        {
            "by_asset_class": by_class,
            "by_sector": _exposure(result.targets, "sector"),
            "by_industry": _exposure(result.targets, "industry"),
            "by_country": _exposure(result.targets, "country"),
            "cash_weight": result.metrics.cash_weight,
        },
    )
    _write_json(
        paths["orders_preview"],
        {
            "paper_only": True,
            "quantity_coverage": result.metrics.price_coverage,
            "orders": [
                asdict(item)
                for item in result.actions
                if item.action != "HOLD" and abs(item.trade_value) > 0
            ],
        },
    )
    return {name: str(path) for name, path in paths.items()}
