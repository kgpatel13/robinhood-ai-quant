Phase 11.1 Feature Intelligence — Installation
==============================================

1. Extract the patch over the current v0.11.0 project.
2. Reinstall:

   pip install -e ".[dev]"

3. Run the integrated smoke/quality gate:

   powershell -ExecutionPolicy Bypass `
     -File .\scripts\phase11_smoke_test.ps1

4. Run full feature intelligence:

   python .\scripts\phase11_feature_intelligence.py `
     --dataset .\data\ml_dataset\training_dataset.parquet `
     --output .\reports\phase11_feature_intelligence

Expected sign-off:
- status: FEATURE_INTELLIGENCE_COMPLETE
- approved_for_label_validation: true
- approved_for_model_training: false

Review feature_recommendations.csv, feature_redundancy.csv,
feature_predictiveness.csv, feature_drift.csv, leakage_diagnostics.csv,
and phase11_feature_signoff.json before Phase 11.2.
