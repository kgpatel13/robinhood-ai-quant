# Phase 7.10 — Promotion Engine Completion

Phase 7.10 replaces placeholder promotion metrics with evidence computed from each
strategy/symbol candidate directory beside `strategy_tournament.csv`.

- Cross-asset consistency is the fraction of tested assets with positive OOS excess CAGR.
- Regime score is the fraction of sufficiently represented market regimes with positive compounded OOS strategy return.
- Monte Carlo survival bootstraps walk-forward window returns and measures the probability of a positive compounded result.

Missing evidence is explicitly marked as `missing` and is never presented as a computed result.

New reports: `regime_validation.csv` and `monte_carlo_validation.csv`.
