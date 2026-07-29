Atlas v4.3.3 — Phase 13.1–13.3

Added:
- src/alpha_engine
- src/microstructure
- src/paper_analytics
- src/research_journal
- tests/unit/test_phase131_133_alpha_execution_intelligence.py
- docs/PHASE13_1_TO_13_3_ALPHA_EXECUTION_INTELLIGENCE.md

Live trading remains disabled. These components are research and paper-trading only.

Validate locally:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
