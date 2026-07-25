# Phase 11.1 — Feature Intelligence and Dataset Diagnostics

Phase 11.1 analyzes the point-in-time dataset created by Phase 11.0. It does not
train models, modify the dataset, or authorize paper/live trading.

## Run

```powershell
python .\scripts\phase11_feature_intelligence.py `
  --dataset .\data\ml_dataset\training_dataset.parquet `
  --output .\reports\phase11_feature_intelligence
```

The default analysis uses a deterministic sample of at most 200,000 rows for
computationally expensive diagnostics. Coverage reports always use the complete
dataset.

## Artifacts

- `feature_summary.csv`: missingness, finite values, variance, quantiles, skewness.
- `feature_outliers.csv`: robust median-absolute-deviation outlier rates.
- `feature_correlations.csv`: Spearman feature correlation matrix.
- `feature_redundancy.csv`: feature pairs above the configured correlation threshold.
- `feature_predictiveness.csv`: univariate Pearson/Spearman relationships, discretized
  mutual information, quantile return spread, and monotonicity.
- `feature_drift.csv`: annual Kolmogorov-Smirnov and median-shift drift diagnostics.
- `feature_stability.csv`: target-relationship stability by asset class and horizon.
- `coverage_report.csv`: complete-dataset coverage by symbol, class, horizon, regime,
  and year.
- `leakage_diagnostics.csv`: hard checks for missing/infinite/constant features and
  suspicious target correlation.
- `feature_recommendations.csv`: KEEP, KEEP_WITH_WINSORIZATION, REVIEW, or REMOVE.
- `feature_dashboard.json`: compact totals for review.
- `phase11_feature_signoff.json`: gate for Phase 11.2 label intelligence.

Recommendations are diagnostic guidance. Phase 11.1 never removes features
automatically. Model training remains blocked until label intelligence is complete.
