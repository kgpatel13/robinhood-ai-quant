# Phase 4 — Multi-Asset Portfolio Research

Phase 4 extends the single-asset Phase 3 backtester into a broker-independent portfolio research
engine. It remains simulation-only and cannot place orders.

## Capabilities

- Synchronized multi-asset backtests over the common date range
- Equal-weight, fixed-weight, and inverse-volatility allocation
- Daily, weekly, or monthly rebalancing
- Maximum per-asset weight and cash-buffer controls
- Next-bar-open execution with commissions and slippage
- Per-symbol holdings, target weights, order ledger, and realized P&L
- Portfolio equity, drawdown, allocation charts, CSV exports, JSON metrics, and HTML report

## Example

```powershell
python -m src.main portfolio-backtest-run `
  --asset SPY=data\validated\stock\SPY.parquet `
  --asset QQQ=data\validated\stock\QQQ.parquet `
  --asset BTC-USD=data\validated\crypto\BTC-USD.parquet `
  --strategy moving_average_cross `
  --fast 20 `
  --slow 100 `
  --allocation inverse_volatility `
  --vol-lookback 30 `
  --rebalance weekly `
  --max-asset-weight 0.60 `
  --cash-buffer-pct 0.02
```

All assets must have overlapping daily bars. The engine uses only timestamps common to every input
dataset so that one asset cannot receive information unavailable to another.

## Research limitations

- Fractional quantities are assumed.
- Corporate actions depend on the normalized source data.
- Taxes, borrow costs, margin, leverage, short selling, and options are excluded.
- Rebalancing uses simulated market orders at the next open.
- Results are not a forecast and should not be interpreted as investment advice.
