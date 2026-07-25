Phase 11.3-11.9 Model Intelligence v0.11.9

1. Preserve your local .env, data, reports, .git, and .venv directories.
2. Copy this build over the existing project.
3. Run:

   pip install -e ".[dev]"
   python -m ruff format .
   python -m ruff check .
   python -m mypy .
   python -m pytest
   powershell -ExecutionPolicy Bypass -File .\scripts\phase11_smoke_test.ps1

4. Run the complete Phase 11 model analysis:

   python .\scripts\phase11_model_intelligence.py `
     --dataset .\data\ml_dataset\training_dataset.parquet `
     --label-signoff .\reports\phase11_label_intelligence\phase11_label_signoff.json `
     --output .\reports\phase11_model_intelligence

Phase 12 review is allowed only when phase11_final_signoff.json reports at least one candidate horizon.
Paper and live trading remain blocked.
