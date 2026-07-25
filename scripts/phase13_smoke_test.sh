#!/usr/bin/env bash
set -euo pipefail
python scripts/phase13_portfolio_engine.py \
  --trades reports/phase12_research_validation_smoke/simulated_trades.csv \
  --output reports/phase13_portfolio_engine_smoke
python -m ruff format --check .
python -m ruff check .
python -m mypy .
python -m pytest
echo "Phase 13.9 quality gate passed."
