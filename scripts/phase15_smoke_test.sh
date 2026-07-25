#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import zipfile
zipfile.ZipFile('phase12_research_validation_reports.zip').extract('simulated_trades.csv', 'reports/phase15_smoke_input')
PY
python scripts/phase15_alpha_engine.py --trades reports/phase15_smoke_input/simulated_trades.csv --output reports/phase15_alpha_engine_smoke --folds 3 --minimum-train-rows 500
python -m ruff format --check .
python -m ruff check .
python -m mypy .
python -m pytest
echo "Phase 15.9 quality gate passed."
