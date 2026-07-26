Phase 18.5 Soft Adaptive Optimizer (v0.18.5)

Copy the archive contents into the project root and replace matching files.

Validation:
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Run:
  Remove-Item -Recurse -Force .\reports\phase18_5_soft_optimizer -ErrorAction SilentlyContinue
  python .\scripts\phase18_adaptive_optimizer.py

Input dependency:
  reports\phase17_execution_intelligence\execution_scores.csv
  reports\phase17_execution_intelligence\phase17_equity_curve.csv
  reports\phase17_execution_intelligence\phase17_executed_trades.csv

Research only. Paper and live trading remain disabled.
