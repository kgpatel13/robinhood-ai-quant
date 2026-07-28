Phase 6.0-6.2 - Intraday Research and Paper-Trading Engine

Included:
- timezone-aware minute-bar normalization and quality checks
- deterministic intraday momentum/volume strategy
- cost-aware intraday backtester
- regular-session gate
- end-of-day forced flattening
- paper-only decision orchestrator with no broker submission method
- platform version updated to 3.6.0

Validation:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest

Live order submission remains intentionally unavailable.
