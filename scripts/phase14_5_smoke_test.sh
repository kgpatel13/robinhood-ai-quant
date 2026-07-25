#!/usr/bin/env bash
set -euo pipefail

echo "==> Phase 14.5 repaired portfolio engine smoke run"
python scripts/phase13_portfolio_engine.py \
  --trades reports/phase12_research_validation_smoke/simulated_trades.csv \
  --output reports/phase13_portfolio_engine_smoke

echo "==> Phase 14 research intelligence against repaired smoke output"
python scripts/phase14_research_intelligence.py \
  --executed-trades reports/phase13_portfolio_engine_smoke/executed_trades.csv \
  --rejected-signals reports/phase13_portfolio_engine_smoke/rejected_signals.csv \
  --equity-curve reports/phase13_portfolio_engine_smoke/portfolio_equity_curve.csv \
  --output reports/phase14_research_intelligence_smoke

python -m ruff format --check .
python -m ruff check .
python -m mypy .
python -m pytest
echo "Phase 14.5 quality gate passed."
