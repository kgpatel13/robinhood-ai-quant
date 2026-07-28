Atlas Phase 7.9-8.5 compatibility patch

Replace:
  src/analytics/performance.py

This restores calculate_metrics() for the original backtest and portfolio engines
and fixes the covariance scalar typing issue in compare_benchmark().

After extraction run:
  python -m ruff format .
  python -m ruff check . --fix
  python -m mypy .
  python -m pytest
