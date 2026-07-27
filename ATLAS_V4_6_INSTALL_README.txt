Atlas Phase 4.6 - Point-in-Time Historical Snapshot Engine

Install
1. Extract this patch into the robinhood-ai-quant project root.
2. Allow replacement of src/atlas/portfolio/__init__.py.
3. Run the validation commands below.

Validation
python -m ruff check src tests scripts
python -m mypy src
python -m pytest

Build point-in-time snapshots
python -m scripts.atlas_v4_point_in_time

Optional faster validation run
python -m scripts.atlas_v4_point_in_time --maximum-assets 250

Outputs
reports/atlas_v4/point_in_time/snapshot_manifest.json
reports/atlas_v4/point_in_time/leakage_audit.json
reports/atlas_v4/point_in_time/snapshot_coverage.csv
reports/atlas_v4/point_in_time/snapshots/ranked_assets_YYYY-MM-DD.csv

Research boundary
Price, volume, momentum, volatility, trend, and liquidity features are computed only
from market rows dated on or before each snapshot date. Current metadata fields such
as sector, industry, country, and market cap are preserved for compatibility but are
explicitly marked as not historically versioned. Fundamentals are not backfilled.
