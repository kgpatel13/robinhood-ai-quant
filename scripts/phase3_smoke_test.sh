#!/usr/bin/env bash
set -euo pipefail
PYTHON=".venv/bin/python"
"$PYTHON" -m src.main data-demo --symbol PHASE3-DEMO --rows 400
"$PYTHON" -m src.main backtest-run \
  --path data/validated/stock/PHASE3-DEMO.parquet \
  --strategy moving_average_cross --fast 20 --slow 50
printf '\nPhase 3 smoke test passed.\n'
