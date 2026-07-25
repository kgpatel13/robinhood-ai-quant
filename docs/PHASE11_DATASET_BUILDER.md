# Phase 11.0 — Point-in-Time Dataset Builder

Phase 11.0 creates a reusable machine-learning dataset directly from validated OHLCV files. It does not consume Phase 10 replay output, train models, connect to a broker, or authorize paper/live trading.

## Outputs

- `data/ml_dataset/training_dataset.parquet`
- `reports/phase11_dataset/dataset_summary.csv`
- `reports/phase11_dataset/label_summary.csv`
- `reports/phase11_dataset/dataset_audit.csv`
- `reports/phase11_dataset/feature_schema.json`
- `reports/phase11_dataset/dataset_failures.json`
- `reports/phase11_dataset/manifest.json`
- `reports/phase11_dataset/phase11_dataset_signoff.json`

## Run

```powershell
python .\scripts\phase11_dataset.py `
  --data-root .\data\validated `
  --dataset .\data\ml_dataset\training_dataset.parquet `
  --output .\reports\phase11_dataset
```

## Quality gate

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\phase11_smoke_test.ps1
```

The builder uses features available on the signal bar, enters on the next bar open, and derives labels only from subsequent bars. A failed audit blocks writing the training dataset.
