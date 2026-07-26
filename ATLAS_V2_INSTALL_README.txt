ATLAS AI v2.0.0 - RESEARCH INTELLIGENCE FOUNDATION

This patch begins the combined v2 milestone:
- reproducible experiment manifests
- configuration and dataset fingerprints
- locked Phase 18.6 baseline fingerprint
- stock and crypto universe ingestion
- liquidity eligibility filtering
- market regime classification
- strategy selection for momentum swing, mean reversion, intraday momentum, or cash
- explainable multi-factor Alpha Score ranking
- paper/live trading hard-disabled

INSTALL
1. Extract this ZIP into C:\Projects\robinhood-ai-quant
2. Select "Replace files in destination".
3. Activate the virtual environment and run:

   pip install -e ".[dev]"
   python -m ruff format .
   python -m ruff check .
   python -m mypy .
   python -m pytest

INPUT FILES
Create these files before the production research run:
- data\universe\stocks.csv
- data\universe\crypto.csv

Required CSV columns:
symbol,price,average_daily_volume,return_1d,return_5d,return_20d,volatility_20d,distance_from_20d_high,relative_volume,spread_bps

RUN
python .\scripts\atlas_v2_research_intelligence.py

OUTPUT
reports\atlas_v2\opportunity_ranking.json
reports\atlas_v2\atlas_dashboard.json
reports\atlas_v2\experiment_manifest.json

SAFETY
This release does not place orders. Paper and live trading remain disabled.

ATLAS AI v2.1 — UNIVERSE INTELLIGENCE
=====================================

This update adds an incremental local asset registry and two independent discovery providers:

- U.S. listed securities from Nasdaq Trader's official symbol directory.
- Crypto market assets from CoinGecko's /coins/markets endpoint.

Set your CoinGecko Demo API key in PowerShell before running both providers:

    $env:COINGECKO_DEMO_API_KEY="your-demo-key"

Update both universes:

    python scripts\atlas_v2_1_universe_intelligence.py

Stocks only (no API key required):

    python scripts\atlas_v2_1_universe_intelligence.py --stocks-only

Crypto only:

    python scripts\atlas_v2_1_universe_intelligence.py --crypto-only

Generated local artifacts:

    data\universe\registry.json
    data\universe\registry.csv
    reports\atlas_v2\universe_update.json

Safety behavior:

- A failed provider never deactivates that provider's existing assets.
- Registry files are replaced atomically after a successful update.
- ETFs, warrants, rights, units, preferred/depositary issues and test issues remain
  discoverable where appropriate but are not marked tradable by Atlas.
- No orders are created or transmitted.
