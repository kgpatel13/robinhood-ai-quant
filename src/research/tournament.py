from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from src.research.models import OptimizationConfig, ParameterSpec
from src.research.phase5 import run_phase5_bundle
from src.research.walk_forward import WalkForwardConfig
from src.strategies import available_strategies, strategy_parameter_space


def _optimization_for(strategy: str, template: OptimizationConfig) -> OptimizationConfig:
    parameters = tuple(
        ParameterSpec(item.name, item.values) for item in strategy_parameter_space(strategy)
    )
    return replace(template, strategy=strategy, parameters=parameters)


def run_strategy_tournament(
    data_root: Path,
    symbols: list[str],
    optimization_template: OptimizationConfig,
    walk_forward: WalkForwardConfig,
    output_root: Path,
    strategies: list[str] | None = None,
    crypto_fee_bps: float = 25.0,
    crypto_slippage_bps: float = 10.0,
) -> dict[str, object]:
    selected = strategies or available_strategies()
    rows: list[pd.DataFrame] = []
    output_root.mkdir(parents=True, exist_ok=True)
    for strategy in selected:
        strategy_output = output_root / strategy
        run_phase5_bundle(
            data_root,
            symbols,
            _optimization_for(strategy, optimization_template),
            walk_forward,
            strategy_output,
            crypto_fee_bps=crypto_fee_bps,
            crypto_slippage_bps=crypto_slippage_bps,
        )
        leaderboard = pd.read_csv(strategy_output / "phase5_leaderboard.csv")
        leaderboard.insert(0, "strategy", strategy)
        rows.append(leaderboard)
    combined = pd.concat(rows, ignore_index=True).sort_values(
        ["score", "oos_sharpe_ratio"], ascending=False
    )
    combined.to_csv(output_root / "strategy_tournament.csv", index=False)
    (output_root / "strategy_tournament.json").write_text(
        combined.to_json(orient="records", indent=2), encoding="utf-8"
    )
    champions = (
        combined.sort_values(
            ["symbol", "score", "oos_sharpe_ratio"],
            ascending=[True, False, False],
        )
        .groupby("symbol", as_index=False)
        .first()
    )
    champions.to_csv(output_root / "asset_champions.csv", index=False)
    return {"strategies": len(selected), "evaluations": len(combined), "output": str(output_root)}
