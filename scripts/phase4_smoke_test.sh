#!/usr/bin/env bash
set -euo pipefail

python -m src.main data-demo --symbol PHASE4-A --rows 400
python -m src.main data-demo --symbol PHASE4-B --rows 400
python -m src.main portfolio-backtest-run \
  --asset PHASE4-A=data/validated/stock/PHASE4-A.parquet \
  --asset PHASE4-B=data/validated/stock/PHASE4-B.parquet \
  --strategy moving_average_cross \
  --fast 20 \
  --slow 50 \
  --allocation equal \
  --rebalance weekly \
  --max-asset-weight 0.60 \
  --report-name phase4_smoke

echo "Phase 4 portfolio smoke test passed."
