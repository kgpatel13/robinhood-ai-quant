#!/usr/bin/env bash
set -euo pipefail

echo "==> Phase 11.0 dataset smoke build"
python scripts/phase11_dataset.py --data-root data/validated --dataset data/ml_dataset/phase11_smoke.parquet --output reports/phase11_dataset_smoke --symbols AAPL BTC-USD --stride 10

echo "==> Phase 11.1 feature intelligence smoke run"
python scripts/phase11_feature_intelligence.py --dataset data/ml_dataset/phase11_smoke.parquet --output reports/phase11_feature_intelligence_smoke --maximum-rows 10000

echo "==> Phase 11.2.2 label intelligence smoke run"
python scripts/phase11_label_intelligence.py --dataset data/ml_dataset/phase11_smoke.parquet --output reports/phase11_label_intelligence_smoke --maximum-rows 10000 --minimum-horizon-rows 100

echo "==> Phase 11.3-11.9 model intelligence smoke run"
python scripts/phase11_model_intelligence.py --dataset data/ml_dataset/phase11_smoke.parquet --label-signoff reports/phase11_label_intelligence_smoke/phase11_label_signoff.json --output reports/phase11_model_intelligence_smoke --maximum-rows-per-horizon 2000 --minimum-train-rows 500

echo "==> Ruff format check"
python -m ruff format --check .
echo "==> Ruff lint check"
python -m ruff check .
echo "==> Mypy check"
python -m mypy .
echo "==> Pytest suite"
python -m pytest

echo "Phase 11.9 quality gate passed."
