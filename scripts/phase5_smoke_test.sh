#!/usr/bin/env bash
set -euo pipefail
python -m compileall -q src scripts
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python scripts/phase5_bundle.py --symbols SPY QQQ BTC-USD --output reports/phase5_smoke
echo "Phase 5 complete smoke test passed."
