from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.atlas.portfolio.core import (
    CurrentPosition,
    PortfolioCandidate,
    PortfolioResult,
    finite_number,
)


def read_candidates(
    ranked_assets_path: Path,
    feature_store_path: Path | None = None,
) -> list[PortfolioCandidate]:
    features: dict[str, dict[str, float | None]] = {}
    if feature_store_path and feature_store_path.exists():
        with feature_store_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                asset_id = row.get("asset_id", "")
                if asset_id:
                    features[asset_id] = {
                        "volatility_60d": finite_number(row.get("volatility_60d")),
                        "price": finite_number(row.get("close")) or finite_number(row.get("price")),
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
            raise ValueError(f"Ranked assets are missing required columns: {sorted(required)}")
        for row in reader:
            asset_id = row["asset_id"]
            candidate_features = features.get(asset_id, {})
            candidates.append(
                PortfolioCandidate(
                    rank=int(row["rank"]),
                    asset_id=asset_id,
                    symbol=row["symbol"],
                    asset_class=row["asset_class"],
                    alpha_score=float(row["alpha_score"]),
                    alpha_percentile=float(row["alpha_percentile"]),
                    confidence=row["confidence"],
                    volatility_60d=candidate_features.get("volatility_60d"),
                    price=candidate_features.get("price"),
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


def write_reports(result: PortfolioResult, output_directory: Path) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "portfolio": output_directory / "portfolio.json",
        "portfolio_metrics": output_directory / "portfolio_metrics.json",
        "risk_report": output_directory / "risk_report.json",
        "rebalance_plan": output_directory / "rebalance_plan.json",
        "allocation_summary": output_directory / "allocation_summary.json",
        "orders_preview": output_directory / "orders_preview.json",
    }
    _write_json(paths["portfolio"], {"positions": [asdict(item) for item in result.targets]})
    _write_json(paths["portfolio_metrics"], asdict(result.metrics))
    _write_json(
        paths["risk_report"],
        {
            "largest_position_weight": result.metrics.largest_position_weight,
            "crypto_weight": result.metrics.crypto_weight,
            "concentration_hhi": result.metrics.concentration_hhi,
            "effective_positions": result.metrics.effective_positions,
            "estimated_volatility": result.metrics.estimated_volatility,
            "excluded_assets": dict(result.excluded),
        },
    )
    _write_json(paths["rebalance_plan"], {"actions": [asdict(item) for item in result.actions]})
    by_class: dict[str, float] = {}
    for position in result.targets:
        by_class[position.asset_class] = (
            by_class.get(position.asset_class, 0.0) + position.target_weight
        )
    _write_json(
        paths["allocation_summary"],
        {"by_asset_class": by_class, "cash_weight": result.metrics.cash_weight},
    )
    _write_json(
        paths["orders_preview"],
        {
            "paper_only": True,
            "orders": [
                asdict(item)
                for item in result.actions
                if item.action != "HOLD" and abs(item.trade_value) > 0
            ],
        },
    )
    return {name: str(path) for name, path in paths.items()}
