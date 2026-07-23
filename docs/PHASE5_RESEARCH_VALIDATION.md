# Phase 5 Research and Validation

Phase 5 is the evidence gate between strategy development and the Phase 6 strategy factory.

## Included

- canonical dataset discovery and fail-fast quality validation;
- optimization with grid/random search;
- transaction costs and slippage;
- entries, exits, completed trades, open positions, realized and unrealized P&L;
- buy-and-hold benchmark, alpha, beta, correlation, excess return and exposure;
- rolling walk-forward optimization with combined out-of-sample equity;
- parameter stability utility;
- multi-asset tournament reports;
- objective research scorecard and promotion status.

## Run

```powershell
python .\scripts\phase5_bundle.py --symbols SPY QQQ BTC-USD
```

Full configured universe:

```powershell
python .\scripts\phase5_bundle.py
```

Outputs are written under `reports/phase5`.

No backtest directly qualifies a strategy for live trading. The highest Phase 5 status is
`PAPER-TRADING ELIGIBLE`.
