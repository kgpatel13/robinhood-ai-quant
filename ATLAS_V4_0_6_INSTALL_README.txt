Atlas v4.0.6 — Phase 10.4–10.6 Production Operations Foundation

Adds:
- Typed priority event bus, JSONL event store, dead-letter capture and replay
- US equity session classifier and strategy operating profiles
- Interval scheduler with missed-run catch-up behavior
- Health monitoring and component heartbeats
- Atomic JSON checkpoints and restart recovery primitives
- Metrics collection, stale-data guard and paper-trading kill switch

Safety boundary:
PAPER ONLY. LIVE ORDER ROUTING REMAINS DISABLED.

Validate:
python -m pip install -e ".[dev,dashboard]"
python -m ruff format .
python -m ruff check . --fix
python -m mypy .
python -m pytest
