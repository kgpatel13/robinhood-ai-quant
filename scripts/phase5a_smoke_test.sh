#!/usr/bin/env bash
set -euo pipefail
python -m src.main data-demo --symbol OPTDEMO --rows 120
python -m src.main optimize-run --path data/validated/stock/OPTDEMO.parquet --param fast_period=5,10 --param slow_period=20,30 --method grid --objective sharpe --report-name phase5a_smoke
python -m pytest tests/unit/test_research_search.py tests/unit/test_research_objectives.py tests/unit/test_research_engine.py tests/unit/test_research_report.py tests/integration/test_optimization_cli.py
echo "Phase 5A optimization smoke test passed."
