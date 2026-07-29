Atlas v4.2.6 — Phase 12.4–12.6 Strategy Performance Intelligence

Install:
  pip install -e ".[dev,dashboard]"

Validate:
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Expected test count: 304 passed.

New packages:
  src/feature_intelligence
  src/execution_costs
  src/strategy_intelligence

Safety: research and paper-deployment recommendations only; no broker order submission.
