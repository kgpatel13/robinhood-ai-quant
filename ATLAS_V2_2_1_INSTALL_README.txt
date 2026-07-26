Atlas AI v2.2.1 — Historical Market Data Engine

Install
1. Extract this ZIP into the repository root and allow file replacement.
2. Run: pip install -e ".[dev]"
3. Run: ruff check .
4. Run: mypy .
5. Run: pytest
6. Run: python scripts\atlas_v2_2_1_history.py
7. Run: python scripts\atlas_v2_2_market_intelligence.py

Default controlled acquisition scope
- 100 tradable stocks
- 50 crypto assets by registry market cap
- 730 calendar days of daily history

Configuration keys are in config/atlas_v2.yaml.
History files are written atomically under data/market/daily.
The update is incremental: subsequent runs request dates after the latest stored bar.
