# Phase 11.1–11.3 — Atlas ML Platform

This release adds a controlled machine-learning lifecycle while preserving the paper-only safety boundary.

## Phase 11.1 — Feature Store

- Versioned feature-set definitions
- Parquet-backed offline storage
- Content hashes and metadata
- Point-in-time reads
- Latest feature row per entity
- Duplicate entity/timestamp protection

## Phase 11.2 — Model Registry

- Candidate, challenger, champion and archived stages
- Atomic stage transitions
- Champion replacement
- Rollback to archived versions
- Protected champion deletion
- Joblib artifacts and JSON metadata

## Phase 11.3 — Automated Training

- Deterministic hyperparameter search
- Existing expanding-window time-series validation
- Champion/challenger comparison
- Metric-based promotion policy
- Population Stability Index drift detection
- Reproducible run identifiers and model metadata

## Safety

This phase does not enable live trading. Models must pass paper-trading and operational validation before any future live-broker work.
