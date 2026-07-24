from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from src.backtest import BacktestConfig, BacktestEngine
from src.research.validation import discover_datasets
from src.strategies import EnsembleStrategy, create_strategy, strategy_defaults


def run_strategy_portfolio(
    data_root: Path,
    symbols: list[str],
    strategy_names: list[str],
    output_root: Path,
    threshold: float = 0.5,
    backtest_config: BacktestConfig | None = None,
    crypto_fee_bps: float = 25.0,
    crypto_slippage_bps: float = 10.0,
) -> dict[str, object]:
    registry = discover_datasets(data_root)
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    base_config = backtest_config or BacktestConfig(slippage_bps=5.0, fee_bps=1.0)
    for symbol in symbols:
        bars = pd.read_parquet(registry[symbol])
        config = base_config
        if registry[symbol].parent.name == "crypto":
            config = replace(
                base_config,
                fee_bps=crypto_fee_bps,
                slippage_bps=crypto_slippage_bps,
            )
        members = tuple(create_strategy(name, **strategy_defaults(name)) for name in strategy_names)
        result = BacktestEngine().run(bars, EnsembleStrategy(members, threshold), config)
        symbol_dir = output_root / symbol.replace("/", "-")
        symbol_dir.mkdir(parents=True, exist_ok=True)
        result.equity_curve.to_csv(symbol_dir / "equity.csv", index=False)
        result.trades.to_csv(symbol_dir / "trades.csv", index=False)
        payload = {
            "symbol": symbol,
            "strategies": strategy_names,
            "backtest_config": {
                "initial_cash": config.initial_cash,
                "commission_per_trade": config.commission_per_trade,
                "slippage_bps": config.slippage_bps,
                "fee_bps": config.fee_bps,
                "max_exposure": config.max_exposure,
            },
            "metrics": result.metrics,
        }
        (symbol_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        rows.append({"symbol": symbol, **result.metrics})
    pd.DataFrame(rows).to_csv(output_root / "strategy_portfolio_summary.csv", index=False)
    return {"symbols": len(rows), "strategies": len(strategy_names), "output": str(output_root)}
