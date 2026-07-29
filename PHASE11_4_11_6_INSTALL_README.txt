Atlas v4.1.6 - Phase 11.4-11.6

Adds:
- Weighted ensemble decision engine with abstention and disagreement controls
- Adaptive confidence/volatility/drawdown-aware position sizing
- Portfolio concentration, exposure, and heat controls
- Integrated paper-only order proposal pipeline

Validation commands:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
