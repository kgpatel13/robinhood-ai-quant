Atlas v4.5.3 - Phase 15.1-15.3

1. Extract over the prior project or use this ZIP as the complete project.
2. Activate the Python 3.12 virtual environment.
3. Run: pip install -e ".[dev,dashboard]"
4. Run: python -m ruff check src tests scripts
5. Run: python -m mypy src
6. Run: python -m pytest

New modules remain broker-independent. No live trade can be submitted by this release.
