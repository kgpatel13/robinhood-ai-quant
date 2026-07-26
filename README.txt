Atlas AI v3.0 Phase 4 - MyPy Fix

Fixes the two union-attr errors in src/atlas/portfolio/engine.py by explicitly
narrowing target/current before accessing symbol and asset_class.

Installation:
1. Extract this ZIP over the project root.
2. Allow replacement of src/atlas/portfolio/engine.py.
3. Run:
   python -m mypy src
   python -m pytest
   python -m ruff check src tests scripts

No runtime portfolio logic or configuration is changed.
