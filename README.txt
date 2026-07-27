Atlas AI v3.0 Phase 4.1 MyPy Fix

Replace this file:
  src/atlas/portfolio/io.py

Then run:
  python -m ruff check src tests scripts
  python -m mypy src
  python -m pytest
  python -m scripts.atlas_v4_portfolio --capital 100000

This patch replaces loosely typed dict[str, object] lookups with a TypedDict-backed
feature record and explicit None-aware fallback selection. Runtime behavior is preserved.
