PHASE 4.8.2 - DAILY PAPER-TRADING ORCHESTRATION
================================================

Added:
- src/execution/orchestration.py
- tests/unit/test_execution_phase482.py

Capabilities:
- One idempotent workflow per trading date
- Market-calendar and market-hours gating
- Data-refresh hook
- Target-portfolio generation hook
- Price snapshot hook
- Target weights converted into sell-before-buy rebalance orders
- Broker routing and paper execution
- Persistent daily completion checkpoint
- Healthy/failed heartbeat status
- Optional workflow report callback
- Safe force-rerun support

This module intentionally uses protocols/callbacks so later data, strategy,
regime, ML, and reporting modules plug into the same orchestration contract.

Validate in PowerShell:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
