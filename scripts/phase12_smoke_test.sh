#!/usr/bin/env bash
set -euo pipefail
python scripts/phase12_research_validation.py \
  --dataset data/ml_dataset/phase11_smoke.parquet \
  --phase11-champions reports/phase11_model_intelligence_smoke/champion_models.csv \
  --output reports/phase12_research_validation_smoke \
  --horizons 20 10 --maximum-rows-per-horizon 4000 --folds 2 \
  --minimum-train-timestamps 100
python -m ruff format --check .
python -m ruff check .
python -m mypy .
python -m pytest
echo "Phase 12.9 quality gate passed."
