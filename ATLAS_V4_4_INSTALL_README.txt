ATLAS PHASE 4.4 - CONSOLIDATED INSTITUTIONAL OPTIMIZER

This build adds:
- Correlation-aware candidate selection and replacement history
- Centralized constraint projection and validation
- Equal, score, inverse-volatility, hybrid, risk-parity,
  minimum-variance, maximum-diversification, and HRP optimizers
- Transaction-cost and turnover estimates
- Optimizer comparison, diagnostics, constraints, replacement,
  and explainability reports
- Paper-only optimizer CLI

Run:
  python -m pip install -e ".[dev]"
  python -m ruff check src tests scripts
  python -m mypy src
  python -m pytest
  python -m scripts.atlas_v4_optimizer --capital 100000

Outputs:
  reports/atlas_v4/optimizer/optimizer_comparison.json
  reports/atlas_v4/optimizer/optimizer_constraints.json
  reports/atlas_v4/optimizer/replacement_history.json
  reports/atlas_v4/optimizer/optimizer_explainability.json
  reports/atlas_v4/optimizer/optimizer_diagnostics.json

Safety:
  This module performs research calculations only. It does not submit orders.
