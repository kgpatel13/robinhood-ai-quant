from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.phase7.monte_carlo import simulate_trade_returns
from src.research.phase7.regimes import classify_regimes

_MIN_REGIME_OBSERVATIONS = 20


def _candidate_directory(tournament_csv: Path, strategy: str, symbol: str) -> Path:
    return tournament_csv.parent / strategy / symbol


def _window_returns(candidate: Path) -> list[float]:
    path = candidate / "windows.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    returns: list[float] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        value = metrics.get("strategy_total_return", metrics.get("total_return"))
        if value is not None:
            returns.append(float(value))
    return returns


def _regime_metrics(candidate: Path) -> dict[str, float | int | str]:
    path = candidate / "oos_equity.csv"
    empty: dict[str, float | int | str] = {
        "regime_score": 0.0,
        "regime_coverage": 0,
        "regime_positive_count": 0,
        "regime_metric_source": "missing",
    }
    if not path.exists():
        return empty
    frame = pd.read_csv(path)
    required = {"close", "equity"}
    if frame.empty or not required.issubset(frame.columns):
        return {**empty, "regime_metric_source": "invalid_oos_equity"}
    frame = frame.copy()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["close", "equity"])
    if frame.empty:
        return {**empty, "regime_metric_source": "invalid_oos_equity"}
    labels = classify_regimes(frame)
    returns = frame["equity"].pct_change().fillna(0.0)
    regime_returns: dict[str, float] = {}
    for regime in sorted(str(value) for value in labels.dropna().unique()):
        mask = labels == regime
        if int(mask.sum()) < _MIN_REGIME_OBSERVATIONS:
            continue
        selected_returns = returns.loc[mask].to_numpy(dtype=float)
        regime_returns[regime] = float(np.prod(1.0 + selected_returns) - 1.0)
    coverage = len(regime_returns)
    positive = sum(value > 0.0 for value in regime_returns.values())
    result: dict[str, float | int | str] = {
        "regime_score": float(positive / coverage) if coverage else 0.0,
        "regime_coverage": coverage,
        "regime_positive_count": positive,
        "regime_metric_source": "oos_equity",
    }
    for regime, value in regime_returns.items():
        result[f"regime_return_{regime}"] = value
    return result


def enrich_promotion_metrics(
    frame: pd.DataFrame,
    tournament_csv: Path,
    *,
    runs: int,
    seed: int,
    confidence: float,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    regime_rows: list[dict[str, object]] = []
    monte_carlo_rows: list[dict[str, object]] = []
    enriched_rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        strategy = str(row["strategy"])
        symbol = str(row["symbol"])
        candidate = _candidate_directory(tournament_csv, strategy, symbol)
        regime = _regime_metrics(candidate)
        window_returns = _window_returns(candidate)
        simulation = simulate_trade_returns(
            window_returns, runs=runs, seed=seed, confidence=confidence
        )
        source = "walk_forward_windows" if window_returns else "missing"
        updated: dict[str, object] = {str(key): value for key, value in row.to_dict().items()}
        updated.update(regime)
        updated.update(
            {
                "monte_carlo_survival": simulation.survival_probability,
                "monte_carlo_median_return": simulation.median_return,
                "monte_carlo_lower_return": simulation.lower_return,
                "monte_carlo_upper_return": simulation.upper_return,
                "monte_carlo_median_max_drawdown": simulation.median_max_drawdown,
                "monte_carlo_observations": len(window_returns),
                "monte_carlo_metric_source": source,
            }
        )
        enriched_rows.append(updated)
        regime_rows.append({"strategy": strategy, "symbol": symbol, **regime})
        monte_carlo_rows.append(
            {
                "strategy": strategy,
                "symbol": symbol,
                **asdict(simulation),
                "monte_carlo_observations": len(window_returns),
                "monte_carlo_metric_source": source,
            }
        )
    return pd.DataFrame(enriched_rows), regime_rows, monte_carlo_rows
