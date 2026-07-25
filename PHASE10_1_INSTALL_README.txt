Robinhood AI Quant - Phase 10.1
Version: 0.10.1

Phase 10.1 adds portfolio-aware historical replay on top of Phase 10.

Main changes:
- Independent portfolio simulation per asset class and holding period
- ETF classification separate from individual stocks
- One-position-per-symbol overlap protection
- Portfolio capacity and cooldown controls
- Risk-based position sizing with a maximum position cap
- Daily marked-to-market equity and true portfolio drawdown
- Yearly, monthly, and exposure reports
- Fixed train/validation/test threshold validation
- Trade-level sequential drawdown explicitly renamed as non-portfolio

After replacing the project, run:

  pip install -e ".[dev]"

  powershell -ExecutionPolicy Bypass `
    -File .\scripts\phase10_smoke_test.ps1

Expected quality gate:
- Ruff format passes
- Ruff lint passes
- Mypy passes
- Pytest passes
- Phase 10.1 smoke replay writes the additional portfolio artifacts

Recommended full replay:

  python .\scripts\phase10_bundle.py `
    --data-root .\data\validated `
    --output .\reports\phase10_1_full

Review these files before changing production thresholds:
- portfolio_summary.csv
- year_performance.csv
- walk_forward_results.csv
- skipped_signals.csv
- replay_failures.json
