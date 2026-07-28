Atlas Research Lab — Phase 6.6–7.2
Version 3.7.2

Adds:
- Multi-strategy registry surfaced in the dashboard
- Yahoo Finance and CSV historical-data loaders
- Cost-aware generic strategy backtesting
- Strategy comparison table
- Equity and drawdown curves
- Trade ledger and CSV export
- Existing adaptive market-regime detector integration
- Ensemble construction
- Walk-forward out-of-sample folds

Install:
  python -m pip install -e ".[dev,dashboard]"

Run:
  python -m streamlit run dashboard/app.py

Validate:
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Safety:
  PAPER ONLY. No broker credentials or order-submission implementation is included.
