Robinhood AI Quant - Phase 10 Historical Replay
Version: 0.10.0

Recommended replacement method
1. Back up your current project.
2. Extract the full ZIP over a clean folder, or apply the patch ZIP at the project root.
3. Activate your Python 3.12 virtual environment.
4. Run: python -m pip install -e ".[dev]"
5. Run: powershell -ExecutionPolicy Bypass -File .\scripts\phase10_smoke_test.ps1
6. Run the full replay:
   python .\scripts\phase10_bundle.py --output reports\phase10_full

For a faster first run:
   python .\scripts\phase10_bundle.py --signal-stride 5 --output reports\phase10_stride5

The full ZIP intentionally excludes .env, .git, .venv, data, reports, logs, and caches.
Keep your existing data\validated folder and copy it into the clean project if needed.
