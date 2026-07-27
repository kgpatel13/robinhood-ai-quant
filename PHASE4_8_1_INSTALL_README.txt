PHASE 4.8.1 — PERSISTENT PAPER-TRADING RUNTIME

Added:
- SQLite execution journal (orders, fills, checkpoints, account snapshots)
- Persistent heartbeat state
- PaperBroker export/restore checkpoints
- Restart recovery through PaperTradingRuntime
- Market-session and holiday gating
- Target-weight RebalancePlanner (sell orders before buys)
- Idempotent event persistence
- Focused recovery/runtime tests

Validation completed in the build environment:
- 12 focused Phase 4.8/4.8.1 tests passed
- Python compileall passed

The build environment does not contain Ruff, MyPy, or PyArrow. Run the full
quality gate in your Python 3.12 project environment:

python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
