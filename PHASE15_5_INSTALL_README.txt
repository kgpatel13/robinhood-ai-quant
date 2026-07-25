PHASE 15.1-15.5 ALPHA VALIDATION REPAIR (v0.15.5)

Key changes
- Blocks fold, phase15_fold, raw year, outcome fields, and research identifiers from model features.
- Produces feature_lineage.csv with explicit leakage status.
- Uses dual stock/crypto regime inputs (SPY and BTC-USD when benchmark CSVs exist).
- Falls back to a leakage-safe prior-history proxy and reports that fallback in the dashboard.
- Uses nested walk-forward selection: model and thresholds are selected on validation data, frozen, then tested once.
- Adds expected-net-return regression and expected-value filtering.
- Replays selected trades through the Phase 13 portfolio simulator.
- Adds fold-level portfolio results and strict Phase 16 promotion gates.

Optional benchmark files
  data/benchmarks/SPY.csv
  data/benchmarks/BTC-USD.csv
Each needs Date/date/timestamp plus Close/close/Adj Close.

Validation commands (PowerShell)
  cd C:\Projects\robinhood-ai-quant
  .\.venv\Scripts\Activate.ps1
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Production run
  python .\scripts\phase15_alpha_engine.py `
    --trades .\reports\phase12_research_validation\simulated_trades.csv `
    --output .\reports\phase15_alpha_engine

Upload the regenerated reports/phase15_alpha_engine folder for review.
