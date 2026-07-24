#!/usr/bin/env bash
set -euo pipefail
python scripts/phase9_bundle.py --symbols SPY QQQ BTC-USD --top-n 5 --output reports/phase9_smoke
python -m ruff format --check src scripts tests
python -m ruff check src scripts tests
python -m mypy src scripts
python -m pytest
echo "Phase 9 quality gate passed."
