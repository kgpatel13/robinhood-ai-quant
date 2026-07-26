Phase 17.4 - Execution and Capital Efficiency Intelligence

Copy all files into the project root and replace pyproject.toml.

Run:
pip install -e ".[dev]"
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
python scripts/phase17_execution_intelligence.py

Reports: reports/phase17_execution_intelligence
Research only. No broker orders are submitted.
