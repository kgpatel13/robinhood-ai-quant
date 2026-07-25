Phase 14 v0.14.0

Extract this ZIP into the project root and allow files to merge/replace.

Run:
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Production:
  python .\scripts\phase14_research_intelligence.py

Smoke:
  powershell -ExecutionPolicy Bypass -File .\scripts\phase14_smoke_test.ps1
