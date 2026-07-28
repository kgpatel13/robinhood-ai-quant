Atlas Phase 10.4-10.6 StrEnum Ruff Patch

Replace these files in your project, preserving their paths:
- src/operations/health.py
- src/runtime/events.py
- src/session/models.py

This resolves Ruff UP042 by replacing str + Enum classes with StrEnum.
EventPriority remains int + Enum.

Validate:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
