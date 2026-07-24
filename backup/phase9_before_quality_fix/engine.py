from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase9.features import build_opportunity_features
from src.research.phase9.models import (
    AssetClass,
    MarketProfile,
    Phase9Config,
    Phase9Result,
)
from src.research.phase9.risk import position_plan
from src.research.phase9.scoring import score_opportunity
from src.research.validation import discover_datasets, validate_dataset


def _classify_asset(frame: pd.DataFrame, symbol: str) -> AssetClass:
    if "asset_class" in frame.columns:
        values = {
            str(value).lower() for value in frame["asset_class"].dropna().unique()
        }
        if values & {"crypto", "cryptocurrency"}:
            return "crypto"
    return "crypto" if symbol.upper().endswith(("-USD", "-USDC")) else "stock"


def _profile(config: Phase9Config, asset_class: AssetClass) -> MarketProfile:
    return config.crypto_profile if asset_class == "crypto" else config.stock_profile


def _scan_symbol(symbol: str, path: Path, config: Phase9Config) -> dict[str, object]:
    frame = pd.read_parquet(path)
    validation = validate_dataset(frame, path)
    asset_class = _classify_asset(frame, symbol)
    profile = _profile(config, asset_class)
    features = build_opportunity_features(frame)
    rejection_reasons: list[str] = []
    if validation.rows < profile.minimum_history:
        rejection_reasons.append("insufficient_history")
    if features["price"] < profile.minimum_price:
        rejection_reasons.append("minimum_price")
    if features["average_dollar_volume"] < profile.minimum_dollar_volume:
        rejection_reasons.append("minimum_liquidity")
    if features["atr"] <= 0:
        rejection_reasons.append("invalid_atr")

    score = score_opportunity(features, asset_class, config.news_risk_default)
    if score.total < profile.entry_score:
        rejection_reasons.append("minimum_opportunity_score")
    plan = position_plan(
        features["price"], features["atr"], config.account_equity, score.total, profile
    )
    if plan.quantity <= 0:
        rejection_reasons.append("invalid_position_plan")

    action = "BUY" if not rejection_reasons else "WATCH"
    strength = "STRONG" if score.total >= profile.strong_entry_score else "STANDARD"
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "as_of": str(validation.end),
        "rows": validation.rows,
        "action": action,
        "strength": strength,
        "eligible": not rejection_reasons,
        "opportunity_score": score.total,
        "trend_score": score.trend,
        "momentum_score": score.momentum,
        "volume_score": score.volume,
        "volatility_score": score.volatility,
        "structure_score": score.structure,
        "news_score": score.news,
        **features,
        **asdict(plan),
        "rejection_reasons": ",".join(rejection_reasons),
    }


def run_phase9_scanner(data_root: Path, config: Phase9Config) -> Phase9Result:
    registry = discover_datasets(data_root)
    selected = tuple(config.symbols) if config.symbols else tuple(sorted(registry))
    unknown = sorted(set(selected).difference(registry))
    if unknown:
        raise ValueError(f"Unknown symbols: {unknown}")

    rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for symbol in selected:
        try:
            rows.append(_scan_symbol(symbol, registry[symbol], config))
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    if not rows:
        raise RuntimeError("No symbols were scanned successfully")

    output = config.output_root
    output.mkdir(parents=True, exist_ok=True)
    ranking = pd.DataFrame(rows).sort_values(
        ["eligible", "opportunity_score"], ascending=[False, False]
    )
    ranking_path = output / "opportunity_ranking.csv"
    ranking.to_csv(ranking_path, index=False)

    eligible = ranking[ranking["eligible"]].copy()
    stock = eligible[eligible["asset_class"] == "stock"].head(config.top_n_per_market)
    crypto = eligible[eligible["asset_class"] == "crypto"].head(config.top_n_per_market)
    stock_path = output / "stock_opportunities.csv"
    crypto_path = output / "crypto_opportunities.csv"
    failures_path = output / "scan_failures.json"
    stock.to_csv(stock_path, index=False)
    crypto.to_csv(crypto_path, index=False)
    failures_path.write_text(json.dumps(failures, indent=2), encoding="utf-8")

    manifest = {
        "phase": "9.0.0",
        "mode": "research_scanner",
        "config": asdict(config),
        "scanned": len(ranking),
        "failed": len(failures),
        "eligible": len(eligible),
        "stock_opportunities": len(stock),
        "crypto_opportunities": len(crypto),
        "notes": [
            "Stock and crypto use separate scoring and risk profiles.",
            (
                "Quality thresholds are soft enough for research, while liquidity and risk "
                "remain hard."
            ),
            "Outputs are research candidates, not live orders.",
        ],
        "artifacts": {
            "ranking": str(ranking_path),
            "stock_opportunities": str(stock_path),
            "crypto_opportunities": str(crypto_path),
            "failures": str(failures_path),
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    artifacts: dict[str, str] = {
        "ranking": str(ranking_path),
        "stock_opportunities": str(stock_path),
        "crypto_opportunities": str(crypto_path),
        "failures": str(failures_path),
        "manifest": str(manifest_path),
    }
    return Phase9Result(
        scanned=len(ranking),
        eligible=len(eligible),
        stock_opportunities=len(stock),
        crypto_opportunities=len(crypto),
        output=str(output),
        artifacts=artifacts,
    )
