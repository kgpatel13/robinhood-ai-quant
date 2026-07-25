Phase 12 typing and lint fix

Replace these files in the project root:
- src/research/phase12/analysis.py
- src/research/phase12/engine.py

Then run:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
powershell -ExecutionPolicy Bypass -File .\scripts\phase12_smoke_test.ps1
