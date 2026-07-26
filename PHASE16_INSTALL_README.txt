Phase 16.4 - Adaptive Portfolio Intelligence
Version 0.16.4

This release combines Phase 16.0 through 16.4:
- adaptive volatility/confidence/EV sizing
- fractional Kelly caps
- regime risk budgets
- leakage-safe rolling model health
- correlation-aware sizing penalties
- Phase 13 execution replay
- fold, bootstrap, stress and Phase 15.6 comparison reports

Research only. Paper and live trading remain disabled.

Run:
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest
  python .\scripts\phase16_portfolio_intelligence.py
