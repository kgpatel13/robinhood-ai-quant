from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.backtest import BacktestConfig
from src.research import OptimizationConfig, ParameterSpec, WalkForwardConfig
from src.research.strategy_portfolio import run_strategy_portfolio
from src.research.tournament import run_strategy_tournament
from src.strategies import available_strategies


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 6 strategy factory bundle")
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "BTC-USD"])
    parser.add_argument("--strategies", nargs="+", default=available_strategies())
    parser.add_argument("--data-root", type=Path, default=Path("data/validated"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase6"))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--equity-fee-bps", type=float, default=1.0)
    parser.add_argument("--equity-slippage-bps", type=float, default=5.0)
    parser.add_argument("--crypto-fee-bps", type=float, default=25.0)
    parser.add_argument("--crypto-slippage-bps", type=float, default=10.0)
    parser.add_argument("--max-exposure", type=float, default=1.0)
    args = parser.parse_args()
    template = OptimizationConfig(
        strategy="moving_average_cross",
        parameters=(ParameterSpec("placeholder", (1,)),),
        objective="sharpe",
        workers=args.workers,
        fee_bps=args.equity_fee_bps,
        slippage_bps=args.equity_slippage_bps,
    )
    walk_forward = WalkForwardConfig(training_years=5, testing_years=1, step_years=1)
    tournament = run_strategy_tournament(
        args.data_root,
        args.symbols,
        template,
        walk_forward,
        args.output / "tournament",
        args.strategies,
        crypto_fee_bps=args.crypto_fee_bps,
        crypto_slippage_bps=args.crypto_slippage_bps,
    )
    portfolio = run_strategy_portfolio(
        args.data_root,
        args.symbols,
        args.strategies,
        args.output / "portfolio",
        backtest_config=BacktestConfig(
            initial_cash=args.initial_cash,
            fee_bps=args.equity_fee_bps,
            slippage_bps=args.equity_slippage_bps,
            max_exposure=args.max_exposure,
        ),
        crypto_fee_bps=args.crypto_fee_bps,
        crypto_slippage_bps=args.crypto_slippage_bps,
    )
    print(json.dumps({"tournament": tournament, "portfolio": portfolio}, indent=2))


if __name__ == "__main__":
    main()
