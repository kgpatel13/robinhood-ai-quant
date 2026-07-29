Atlas v4.1.3 — Phase 11.1–11.3 ML Platform

Install:
  python -m pip install -e ".[dev,dashboard]"

Validate:
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Safety boundary:
  PAPER ONLY
  LIVE ORDER ROUTING DISABLED
