# Phase 10 — Historical Signal Replay and Score Validation

Phase 10 converts the Phase 9 point-in-time scanner into a historical, leakage-controlled validation engine.

## Core controls

- Features and Phase 9 scores are calculated at each historical signal close.
- Entry is placed at the next bar open.
- ATR stops and targets are frozen from the signal bar.
- Same-bar stop/target collisions default to the conservative stop-first assumption.
- Gross and net returns are recorded separately.
- Net returns include asset-class-specific spread, slippage, and fees.
- Stocks and crypto retain separate score bands, thresholds, risk geometry, and cost assumptions.

## Outputs

- `signal_replay.csv`: one row per signal and holding-period outcome.
- `score_band_performance.csv`: expectancy, win rate, profit factor, drawdown, MFE, and MAE by score band.
- `threshold_performance.csv`: performance for signals meeting the Phase 9 threshold.
- `symbol_performance.csv`: per-symbol validation.
- `regime_performance.csv`: bull, bear, sideways, and high-volatility analysis.
- `score_monotonicity.csv`: Spearman relationship between score band and return.
- `threshold_recommendations.csv`: evidence-based research candidates; never automatic live changes.
- `replay_failures.json` and `manifest.json`.

## Run

```powershell
python .\scripts\phase10_bundle.py `
  --output reports\phase10_full
```

Faster functional run:

```powershell
python .\scripts\phase10_bundle.py `
  --signal-stride 5 `
  --output reports\phase10_stride5
```

Threshold-only run:

```powershell
python .\scripts\phase10_bundle.py `
  --threshold-only `
  --output reports\phase10_threshold_only
```

## Interpretation

A convincing Phase 10 result should show positive after-cost expectancy, acceptable drawdown, adequate sample size, robustness across symbols and regimes, and generally improving returns as score bands rise. No single metric is sufficient for promotion.

## Phase 10.1 portfolio-aware validation

Phase 10.1 adds chronological portfolio simulation and removes the risk of interpreting
sequentially compounded replay rows as a real portfolio. Each asset class and holding period
is simulated independently with cash, position sizing, one-position-per-symbol controls,
portfolio capacity, cooldowns, daily mark-to-market equity, and true portfolio drawdown.

New artifacts:

- `portfolio_trades.csv`
- `daily_equity.csv`
- `portfolio_summary.csv`
- `skipped_signals.csv`
- `year_performance.csv`
- `monthly_performance.csv`
- `exposure_analysis.csv`
- `walk_forward_results.csv`

The former grouped `maximum_drawdown` field is retained only under the explicit name
`sequential_trade_drawdown_not_portfolio`. Production risk decisions must use the drawdown in
`portfolio_summary.csv`.
