Atlas Phase 4.3 Institutional Portfolio Controls

Run after portfolio construction:
  python -m scripts.atlas_v4_portfolio --capital 100000
  python -m scripts.atlas_v4_institutional

Outputs are written to reports/atlas_v4/institutional and include eligibility,
correlation, transaction cost, risk contribution, stress testing, Monte Carlo,
decision audit, constraint, intelligence, and readiness reports.

The readiness gate can return RESEARCH_READY or BACKTEST_READY. Live trading remains disabled.
