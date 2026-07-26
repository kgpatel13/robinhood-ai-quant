Phase 18.6 - Institutional Validation Framework

Replace the included files in the project root.

Validation:
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Run:
  python scripts/phase18_adaptive_optimizer.py

Output:
  reports/phase18_6_institutional_validation

This release keeps the Phase 18.5 optimizer unchanged and upgrades certification with:
- paired moving-block bootstrap on daily excess returns
- Monte Carlo trade-order and execution-cost stress
- weighted validation scorecard
- hard safety gates for promotion

Paper and live trading remain disabled.
