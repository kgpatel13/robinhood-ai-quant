Atlas v4.3.2 — Institutional Hardening and Integrated Eligibility

This release fixes the issues found in the first Phase 4.3 validation and adds the
next portfolio-selection control.

FIXES
- Ruff line-length/import cleanup in the Phase 4.3 modules and tests.
- Geometric annual-return calculation.
- Correct annualization units for volatility, alpha, tracking error, and ratios.
- Daily-return sanitization/winsorization for bad vendor prints and split artifacts.
- Correct component-variance risk contributions and percentages.
- Capped, dimensionally valid correlation-convergence stress result.
- Deterministic moving-block bootstrap Monte Carlo simulation.
- Transaction costs only counted for accepted trades.
- Return-clipping diagnostics by asset.

NEXT PHASE CHANGE INCLUDED
- Institutional eligibility is now integrated into portfolio construction.
- Ineligible high-ranked assets are rejected before the position limit is filled.
- The engine automatically considers the next-ranked eligible candidate.
- Filters cover minimum price, market cap, liquidity score, and data-quality score.
- CLI controls were added to atlas_v4_portfolio.

VALIDATION
Run:
  python -m pip install -e ".[dev]"
  python -m ruff check src tests scripts
  python -m mypy src
  python -m pytest
  python -m scripts.atlas_v4_portfolio --capital 100000
  python -m scripts.atlas_v4_institutional

Expected effect on the prior sample:
- Implausible 3303% annual return and 5511% volatility are eliminated.
- Sample hardened metrics were approximately 58.1% annual return and 28.7%
  annual volatility. These are descriptive of the current reconstructed sample,
  not evidence of out-of-sample profitability.
- The prior 84% eligibility blocker should disappear after regenerating the
  portfolio, because failed candidates are now replaced during construction.

Important:
Keep paper/live execution disabled. Phase 5 historical validation is still required.
