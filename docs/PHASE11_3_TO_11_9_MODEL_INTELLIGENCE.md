# Phase 11.3–11.9 — Baseline Model Intelligence and Final Research Sign-off

This consolidated stage completes the remaining Phase 11 research workflow.

- **11.3 Split Integrity:** chronological train, validation, and test partitions with purge and embargo gaps.
- **11.4 Baseline Models:** dummy, L2 logistic regression, shallow decision tree, random forest, and histogram gradient boosting.
- **11.5 Probability Diagnostics:** ROC-AUC, average precision, balanced accuracy, log loss, Brier score, and reliability bins.
- **11.6 Threshold Intelligence:** validation-only probability-threshold selection with cost-adjusted trade outcomes.
- **11.7 Robustness:** test-period asset-class and market-regime diagnostics.
- **11.8 Model Selection:** one champion per approved horizon selected exclusively from validation evidence.
- **11.9 Final Sign-off:** held-out test reporting and Phase 12 candidate classification.

The final sign-off does not authorize paper or live trading. It only determines whether one or more model/horizon candidates are suitable for Phase 12 review.

## Run

```powershell
python .\scripts\phase11_model_intelligence.py `
  --dataset .\data\ml_dataset\training_dataset.parquet `
  --label-signoff .\reports\phase11_label_intelligence\phase11_label_signoff.json `
  --output .\reports\phase11_model_intelligence
```

## Primary artifacts

- `temporal_split_audit.csv`
- `baseline_model_metrics.csv`
- `threshold_analysis.csv`
- `probability_calibration.csv`
- `asset_model_robustness.csv`
- `regime_model_robustness.csv`
- `champion_feature_importance.csv`
- `champion_models.csv`
- `phase11_model_dashboard.json`
- `phase11_final_signoff.json`
