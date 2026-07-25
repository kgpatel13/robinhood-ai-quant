# Phase 12.0-12.9 — Walk-Forward Research and Economic Validation

Phase 12 converts the Phase 11 baseline model work into a stricter research gate before any
paper-trading integration.

## Scope

- **12.0** Input and configuration validation
- **12.1** Expanding walk-forward folds
- **12.2** Purge and embargo enforcement
- **12.3** Feature-family experiments
- **12.4** Baseline model comparison per fold
- **12.5** Platt probability calibration on a dedicated calibration partition
- **12.6** Validation-only probability-threshold selection
- **12.7** Non-overlapping per-symbol economic simulation
- **12.8** Portfolio exposure, slippage, commission and drawdown validation
- **12.9** Horizon-level signoff for paper-trading review

## Safety boundary

A passing Phase 12 result permits review for paper trading only. It never authorizes live trading.
The default research horizons are 20 and 10 bars because Phase 11 identified them as the strongest
starting candidates.

## Production command

```powershell
python .\scripts\phase12_research_validation.py `
  --dataset .\data\ml_dataset\training_dataset.parquet `
  --phase11-champions .\reports\phase11_model_intelligence\champion_models.csv `
  --output .\reports\phase12_research_validation `
  --horizons 20 10
```

## Quality gate

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\phase12_smoke_test.ps1
```

## Review package

Share the complete `reports\phase12_research_validation` directory. The final decision is recorded
in `phase12_final_signoff.json`.
