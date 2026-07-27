ATLAS PHASE 4.2.1 - MARKET METADATA ENRICHMENT

What was added
- Resumable stock metadata enrichment through yfinance.
- Atlas taxonomy for crypto: Digital Assets / Cryptocurrency / Global.
- data/market/metadata.csv cache with status and source fields.
- Portfolio CLI automatically merges metadata.csv with features.csv.
- Sector and industry constraints become active when metadata is available.

Run from the project root with the virtual environment active:

1. Build or resume the metadata cache:
   python -m scripts.atlas_v4_metadata

   For a small smoke test first:
   python -m scripts.atlas_v4_metadata --limit 10 --delay-seconds 0

   To refresh every record:
   python -m scripts.atlas_v4_metadata --force

2. Construct the portfolio:
   python -m scripts.atlas_v4_portfolio --capital 100000

3. Validate:
   python -m ruff check src tests scripts
   python -m mypy src
   python -m pytest

Expected portfolio diagnostics after enrichment:
- price_coverage: 1.0
- volatility_coverage: 1.0
- effective_sizing_method: hybrid
- sector_coverage: near 1.0 for stocks plus Atlas crypto taxonomy
- industry_coverage: near 1.0 for stocks plus Atlas crypto taxonomy

Notes
- The metadata command is resumable. Existing complete/partial rows are not downloaded again unless --force is used.
- Provider failures are recorded as status=error and do not stop the full run.
- Keep this paper-only until historical validation and execution controls are complete.
