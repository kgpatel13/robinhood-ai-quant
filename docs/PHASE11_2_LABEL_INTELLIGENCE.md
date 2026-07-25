# Phase 11.2 — Label Intelligence

Phase 11.2 validates the supervised-learning targets produced by the Phase 11.0 point-in-time dataset builder. It evaluates class balance, return distributions, risk/reward behavior, label noise, cross-horizon overlap, asset-class consistency, regime stability, and temporal construction checks.

## Run

```powershell
python .\scripts\phase11_label_intelligence.py `
  --dataset .\data\ml_dataset\training_dataset.parquet `
  --output .\reports\phase11_label_intelligence
```

The `horizon_quality.csv` report ranks each holding period using a bounded label-quality index. A horizon is approved when it meets the configured quality threshold. Recommendations guide Phase 11.3 baseline modeling; they do not authorize paper or live trading.

## Outputs

- `label_summary.csv`
- `horizon_quality.csv`
- `class_balance.csv`
- `return_distribution.csv`
- `risk_reward_distribution.csv`
- `label_noise.csv`
- `label_overlap.csv`
- `horizon_comparison.csv`
- `regime_label_quality.csv`
- `asset_label_quality.csv`
- `leakage_checks.csv`
- `label_dashboard.json`
- `manifest.json`
- `phase11_label_signoff.json`
