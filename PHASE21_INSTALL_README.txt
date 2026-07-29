Atlas v5.1.3 — Phase 21.1-21.3

1. Extract this archive over the existing project.
2. Activate the virtual environment.
3. Run:
   pip install -e ".[dev,dashboard]"
   python -m ruff check src tests scripts
   python -m mypy src
   python -m pytest

Live trading remains disabled by default.
