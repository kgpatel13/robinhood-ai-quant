Phase 15.6 - Benchmark and Risk-Adjusted Alpha Validation
=========================================================

Changed files:
- src/research/phase15/engine.py
- src/research/phase15/models.py
- scripts/download_phase15_benchmarks.py
- pyproject.toml

What Phase 15.6 adds:
- Real SPY and BTC-USD benchmark support.
- CAGR, Sharpe, Sortino, Calmar, and average gross exposure.
- Filtered-versus-baseline paired fold comparisons.
- Bootstrap comparison of executed-trade mean returns.
- Promotion based on risk-adjusted improvement rather than absolute P&L alone.
- Baseline executed-trade and equity-curve artifacts.

Install and validate:
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Download external benchmarks:
  python .\scripts\download_phase15_benchmarks.py --start 2000-01-01

Run Phase 15.6:
  python .\scripts\phase15_alpha_engine.py `
    --trades .\reports\phase12_research_validation\simulated_trades.csv `
    --output .\reports\phase15_alpha_engine

New artifacts:
- baseline_portfolio_executed_trades.csv
- baseline_portfolio_equity_curve.csv
- paired_fold_comparison.csv
- bootstrap_comparison.csv
