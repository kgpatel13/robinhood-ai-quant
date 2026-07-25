# Phase 14 — Research Intelligence and Performance Attribution

Phase 14 removes ambiguity from headline backtest returns. It records the exact evaluation period, calculates annualized performance, and attributes outcomes by asset class, symbol, calendar year, rejection reason, and descriptive market regime.

## Outputs

- `phase14_dashboard.json`
- `phase14_final_signoff.json`
- `asset_class_attribution.csv`
- `symbol_attribution.csv`
- `regime_attribution.csv`
- `yearly_returns.csv`
- `rejection_attribution.csv`
- `trade_regime_assignments.csv`
- `manifest.json`

The regime labels are diagnostics derived from the executed-trade return stream. They are not presented as a causal or independently tradable regime model. Phase 14 does not submit broker orders.
