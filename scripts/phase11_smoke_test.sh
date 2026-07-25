#!/usr/bin/env bash
set -euo pipefail
python scripts/phase11_dataset.py --data-root data/validated --dataset data/ml_dataset/phase11_smoke.parquet --output reports/phase11_dataset_smoke --symbols AAPL BTC-USD --stride 10
python -m ruff format --check .
python -m ruff check .
python -m mypy .
python -m pytest
echo "Phase 11.0 quality gate passed."
