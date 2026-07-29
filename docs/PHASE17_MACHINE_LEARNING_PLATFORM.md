# Phase 17.1–17.3 — Machine Learning Platform

Atlas v4.7.3 adds a versioned market feature pipeline, reusable classification models,
time-series validation, and model-health monitoring. The release remains research and
paper-trading only; live execution is unchanged and disabled.

## Components

- `src.feature_store`: technical features, normalization, metadata, and registry.
- `src.ml_platform`: logistic regression, random forest, gradient boosting, prediction
  confidence, feature importance, and walk-forward validation.
- `src.model_monitor`: classification quality, calibration error, PSI feature drift,
  prediction drift, and retraining recommendations.

All model decisions carry an explicit model version through `PredictionResult`.
