Atlas Phase 4.6 static-analysis replacement fix

Replace these files in the project root:
- src/atlas/portfolio/__init__.py
- src/atlas/portfolio/point_in_time.py

Fixes:
- Ruff I001 import ordering in portfolio/__init__.py
- MyPy dict[Hashable, Any] to dict[str, Any] mismatch in _read_metadata()

Validate:
python -m ruff check src tests scripts
python -m mypy src
python -m pytest
python -m scripts.atlas_v4_point_in_time
