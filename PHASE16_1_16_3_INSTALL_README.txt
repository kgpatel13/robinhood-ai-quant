Atlas v4.6.3 — Phase 16.1–16.3

Replace your existing project with this release, preserve your local .env/config secrets,
then run:

pip install -e ".[dev,dashboard]"
python -m ruff check src tests scripts
python -m mypy src
python -m pytest

Expected test count after the previously validated v4.5.3 baseline: 330 tests.
Live trading remains disabled.
