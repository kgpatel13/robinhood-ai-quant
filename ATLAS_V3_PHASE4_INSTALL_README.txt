Atlas AI v3.0 - Phase 4 Portfolio Intelligence & Construction Engine

Install
-------
Overlay this patch onto the project root, then reinstall editable:

  python -m pip install -e ".[dev]"

Validate
--------
  python -m pytest tests/test_atlas_portfolio.py
  python -m pytest
  python -m ruff check src tests scripts
  python -m mypy src

Run
---
First generate the Phase 3 ranking, then run:

  python -m scripts.atlas_v4_portfolio --capital 100000

Optional existing portfolio JSON:

  {
    "positions": [
      {
        "asset_id": "stock:AAPL",
        "symbol": "AAPL",
        "asset_class": "stock",
        "market_value": 5000
      }
    ]
  }

Example:
  python -m scripts.atlas_v4_portfolio \
    --capital 100000 \
    --cash-reserve 0.05 \
    --max-positions 25 \
    --max-position-pct 0.08 \
    --max-crypto-pct 0.15 \
    --existing-portfolio current_portfolio.json

Outputs
-------
  reports/atlas_v4/portfolio.json
  reports/atlas_v4/portfolio_metrics.json
  reports/atlas_v4/risk_report.json
  reports/atlas_v4/rebalance_plan.json
  reports/atlas_v4/allocation_summary.json
  reports/atlas_v4/orders_preview.json

Safety
------
This phase is research/paper-only. It does not submit broker orders.
