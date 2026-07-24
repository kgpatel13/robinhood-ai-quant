# Phase 6.9 — Research Hardening

Phase 6.9 adds realistic execution assumptions and exposure controls to the Phase 6 strategy factory.

## Changes

- Equity and crypto fees are applied consistently in tournament and portfolio runs.
- Slippage is recorded explicitly as a research cost.
- `BacktestConfig.max_exposure` caps capital allocated when a position is opened.
- Equity curves include gross exposure and exposure ratio.
- Reports include average exposure, peak exposure, total fees, commissions, and slippage.
- Phase 6 CLI exposes cost and exposure assumptions.

## Recommended smoke run

```powershell
python .\scripts\phase6_bundle.py `
  --symbols SPY QQQ BTC-USD `
  --strategies moving_average_cross rsi_mean_reversion donchian_breakout `
  --equity-fee-bps 1 `
  --equity-slippage-bps 5 `
  --crypto-fee-bps 25 `
  --crypto-slippage-bps 10 `
  --max-exposure 0.75 `
  --output reports\phase6_9_smoke
```
