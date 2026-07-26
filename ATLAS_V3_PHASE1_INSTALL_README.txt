Atlas AI v3.0 - Phase 1 Factor Engine
=====================================

Implemented
-----------
- Typed factor registry and metadata
- Default factor families: momentum, trend, low volatility, liquidity,
  mean reversion, and data quality
- Cross-sectional winsorization, z-score normalization, and percentile ranking
- Missing-value and minimum-component controls
- Configurable composite alpha scoring and deterministic ranking
- Factor coverage, distribution statistics, and pairwise correlations
- Unit tests for normalization, factors, alpha, diagnostics, and registry behavior
- Project package version updated to 3.0.0

Install
-------
Extract this patch into the project root and allow files to overwrite.

Validation
----------
python -m pytest tests/test_atlas_factors.py
python -m pytest
python -m ruff check src tests
python -m mypy src

Validation performed in the build environment
---------------------------------------------
- New factor tests: 4 passed
- Python compilation: passed
- Full test suite could not complete in the build environment because pyarrow
  is not installed there. The first integration test failed while pandas tried
  to write a parquet file; this is an environment dependency issue, not a
  factor-engine assertion failure.
- Ruff and MyPy were not installed in the build environment, so run those two
  quality gates in the project's Python 3.12 development environment.

Safety
------
This phase adds research calculations only. It does not enable paper or live
order execution.
