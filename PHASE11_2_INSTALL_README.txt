Phase 11.2 Label Intelligence v0.11.2

1. Extract the patch into the project root and allow file replacement.
2. Reinstall editable dependencies:
   pip install -e ".[dev]"
3. Run the integrated quality gate:
   powershell -ExecutionPolicy Bypass -File .\scripts\phase11_smoke_test.ps1
4. Run the full label analysis:
   python .\scripts\phase11_label_intelligence.py --dataset .\data\ml_dataset\training_dataset.parquet --output .\reports\phase11_label_intelligence
5. Review phase11_label_signoff.json and horizon_quality.csv.

Paper and live trading remain blocked.
