Atlas AI v3.0 — Phase 4.1 Portfolio Hardening Patch

Install
-------
1. Back up the project.
2. Extract this ZIP over the project root and replace matching files.
3. Reinstall editable package if needed:

   python -m pip install -e ".[dev]"

Validation
----------
python -m pytest tests/test_atlas_portfolio.py
python -m pytest
python -m ruff check src tests scripts
python -m mypy src

Run
---
python -m scripts.atlas_v4_portfolio --capital 100000

What changed
------------
- Retains the Phase 4 MyPy union fix.
- Corrects effective-position calculation by normalizing invested weights.
- Adds explicit sizing diagnostics and score-weight fallback when volatility is unavailable.
- Uses median volatility for partial volatility-data gaps.
- Adds price coverage and quantity-status reporting.
- Adds fractional/whole-share quantity controls.
- Adds optional sector and industry limits when metadata is available.
- Adds country/sector/industry exposure reporting.
- Validates identity and supported asset classes.
- Moves detailed excluded assets to excluded_assets.json and keeps a compact summary in risk_report.json.
- Adds two hardening tests (7 Phase 4 tests total).

Important
---------
This remains paper/research-only. It does not place broker orders.
Sector and industry limits can only be enforced when those metadata fields exist in ranked-assets or feature-store input.
