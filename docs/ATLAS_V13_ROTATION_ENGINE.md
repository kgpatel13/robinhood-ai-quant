# Atlas v13 Autonomous Rotation Research Engine

Atlas v13 adds a shared-capital, point-in-time portfolio rotation backtest for long-only
Robinhood-compatible stocks, ETFs, and crypto.

## Objective

- Planned holding horizon: overnight to 30 calendar days.
- Emergency risk exits: allowed at any time.
- Prefer capital-efficient opportunities, not maximum turnover.
- Compare open positions with new opportunities and rotate only when the replacement score
  materially exceeds the continuation score.

## Included strategy families

1. Time-series momentum
2. Donchian/channel breakout with volume confirmation
3. Pullback continuation in a positive trend
4. Short-term reversal with liquidity/volatility controls
5. Cross-sectional relative strength

These are research hypotheses with published market evidence, not guaranteed-profit systems.
Every strategy must pass point-in-time, multi-year, walk-forward, cost, and paper validation.

## Example

```powershell
quant-platform rotation-backtest-run `
  --asset AAPL=data\validated\stock\AAPL.parquet `
  --asset NVDA=data\validated\stock\NVDA.parquet `
  --asset TSLA=data\validated\stock\TSLA.parquet `
  --asset BTC-USD=data\validated\crypto\BTC-USD.parquet `
  --asset ETH-USD=data\validated\crypto\ETH-USD.parquet `
  --asset SOL-USD=data\validated\crypto\SOL-USD.parquet `
  --initial-cash 5000 `
  --min-hold-days 1 `
  --preferred-max-hold-days 10 `
  --max-hold-days 30 `
  --max-positions 4 `
  --risk-per-trade-pct 0.5 `
  --max-position-pct 25 `
  --max-crypto-position-pct 12 `
  --total-crypto-pct 25 `
  --cash-reserve-pct 10 `
  --min-entry-score 62 `
  --rotation-score-improvement 12 `
  --report-name 2025_rotation_test
```

Outputs are written under `reports/rotation/<report-name>/`:

- `metrics.json`
- `trades.csv`
- `equity.csv`
- `decisions.json`

## Important limitations

This release provides the end-to-end historical rotation simulator and decision audit trail.
It does not certify Robinhood-wide live universe discovery or live order placement. Those remain
behind shadow and paper-trading readiness gates.
