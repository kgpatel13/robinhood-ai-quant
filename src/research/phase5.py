from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from src.research.models import OptimizationConfig
from src.research.scorecard import build_scorecard
from src.research.validation import discover_datasets
from src.research.walk_forward import WalkForwardConfig, WalkForwardEngine


def _window_parameter_stability(parameters: list[dict[str, int | float]]) -> float:
    if not parameters:
        return 0.0
    names = sorted(parameters[0])
    scores: list[float] = []
    for name in names:
        values = [item[name] for item in parameters]
        scores.append(Counter(values).most_common(1)[0][1] / len(values))
    return float(sum(scores) / len(scores)) if scores else 0.0


def run_phase5_bundle(
    data_root: Path,
    symbols: list[str],
    optimization: OptimizationConfig,
    walk_forward: WalkForwardConfig,
    output_root: Path,
    crypto_fee_bps: float = 25.0,
    crypto_slippage_bps: float = 10.0,
) -> dict[str, object]:
    registry = discover_datasets(data_root)
    requested = symbols or sorted(registry)
    unknown = sorted(set(requested).difference(registry))
    if unknown:
        raise ValueError(f"Unknown symbols: {unknown}")
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []
    for symbol in requested:
        bars = pd.read_parquet(registry[symbol])
        symbol_optimization = optimization
        if registry[symbol].parent.name == "crypto":
            symbol_optimization = replace(
                optimization,
                fee_bps=crypto_fee_bps,
                slippage_bps=crypto_slippage_bps,
            )
        result = WalkForwardEngine().run(bars, symbol_optimization, walk_forward)
        metrics = dict(result.metrics)
        metrics["parameter_stability"] = _window_parameter_stability(
            [item.parameters for item in result.windows]
        )
        positive_net_windows = sum(
            float(item.metrics.get("total_return", 0.0)) > 0.0 for item in result.windows
        )
        metrics["cost_resilience"] = positive_net_windows / len(result.windows)
        scorecard = build_scorecard(metrics)
        symbol_dir = output_root / symbol.replace("/", "-")
        symbol_dir.mkdir(parents=True, exist_ok=True)
        result.equity_curve.to_csv(symbol_dir / "oos_equity.csv", index=False)
        windows_payload = [
            {
                "train_start": item.train_start.isoformat(),
                "train_end": item.train_end.isoformat(),
                "test_start": item.test_start.isoformat(),
                "test_end": item.test_end.isoformat(),
                "parameters": item.parameters,
                "metrics": item.metrics,
            }
            for item in result.windows
        ]
        (symbol_dir / "windows.json").write_text(
            json.dumps(windows_payload, indent=2), encoding="utf-8"
        )
        payload = {"symbol": symbol, "metrics": metrics, "scorecard": asdict(scorecard)}
        (symbol_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        summary_rows.append(
            {"symbol": symbol, "score": scorecard.score, "status": scorecard.status, **metrics}
        )
    leaderboard = pd.DataFrame(summary_rows).sort_values(
        ["score", "oos_sharpe_ratio"], ascending=False
    )
    leaderboard.to_csv(output_root / "phase5_leaderboard.csv", index=False)
    (output_root / "phase5_leaderboard.json").write_text(
        leaderboard.to_json(orient="records", indent=2), encoding="utf-8"
    )
    return {"symbols": len(summary_rows), "output": str(output_root)}
