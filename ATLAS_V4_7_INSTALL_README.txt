Atlas Phase 4.7 - Institutional Execution Simulator

Install
1. Extract this archive into the robinhood-ai-quant project root.
2. Allow replacement of src/atlas/portfolio/__init__.py.
3. Activate the existing virtual environment.

Validate
python -m ruff check src tests scripts
python -m mypy src
python -m pytest

Run
python -m scripts.atlas_v4_execution --capital 100000

Optional liquidity stress run
python -m scripts.atlas_v4_execution `
  --capital 1000000 `
  --maximum-participation-rate 0.02 `
  --execution-horizon-days 3

Outputs
reports/atlas_v4/execution/execution_fills.csv
reports/atlas_v4/execution/execution_summary.json
reports/atlas_v4/execution/execution_capacity.json
reports/atlas_v4/execution/execution_diagnostics.json

Research boundary
This phase is paper-only. It estimates spread, volatility-linked slippage,
square-root market impact, partial fills, fees, and capacity. It does not send
orders and is not a guarantee of brokerage execution quality.
