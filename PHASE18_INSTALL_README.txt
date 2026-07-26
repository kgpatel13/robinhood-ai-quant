Phase 18.4 Adaptive Portfolio Optimization

Copy these files into the matching project paths and replace pyproject.toml.

Run:
pip install -e ".[dev]"
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
python scripts/phase18_adaptive_optimizer.py

Reports are written to reports/phase18_adaptive_optimizer.
Research only. Paper trading and live trading remain disabled.
