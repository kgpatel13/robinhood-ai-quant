#!/usr/bin/env bash
set -euo pipefail
python scripts/phase10_bundle.py --symbols SPY AAPL BTC-USD --signal-stride 20 --output reports/phase10_smoke
python -m ruff format --check .
python -m ruff check .
python -m mypy src scripts
python -m pytest
echo "Phase 10.4 quality gate passed."
