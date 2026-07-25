# Phase 10.2 — Robustness Validation and Research Sign-off

Phase 10.2 converts the Phase 10.0 trade replay and Phase 10.1 portfolio replay into a promotion-controlled research workflow.

## Added controls

- Rolling train/validation/test walk-forward windows
- Threshold stability analysis across unseen windows
- Incremental transaction-cost stress scenarios
- Passive benchmark comparison (SPY for stock/ETF, BTC-USD for crypto)
- Point-in-time timestamp and value leakage audit
- Explicit promotion/rejection decisions
- Machine-readable research sign-off for Phase 11 paper trading

## New artifacts

- `rolling_walk_forward_results.csv`
- `window_stability.csv`
- `transaction_cost_stress.csv`
- `benchmark_comparison.csv`
- `leakage_audit.csv`
- `promotion_decisions.csv`
- `phase10_research_signoff.json`

## Promotion defaults

A scenario is promoted to Phase 11 paper trading only when it has:

- Positive test performance in at least 60% of valid rolling windows
- Median test profit factor of at least 1.10
- Positive median test average return
- At least 100 out-of-sample trades
- Selected-threshold range no wider than 15 points
- A fully passing leakage audit

Promotion is for paper trading only. Phase 10.2 never approves live trading.
