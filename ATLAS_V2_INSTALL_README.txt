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
