Phase 11.0 Point-in-Time Dataset Builder
========================================

1. Extract the patch over the validated Phase 10.4 project.
2. Reinstall editable dependencies:

   pip install -e ".[dev]"

3. Run the quality gate:

   powershell -ExecutionPolicy Bypass -File .\scripts\phase11_smoke_test.ps1

4. Build the full dataset:

   python .\scripts\phase11_dataset.py `
     --data-root .\data\validated `
     --dataset .\data\ml_dataset\training_dataset.parquet `
     --output .\reports\phase11_dataset

Review phase11_dataset_signoff.json. Model training is allowed only when
approved_for_model_training is true. Paper and live trading remain blocked.
