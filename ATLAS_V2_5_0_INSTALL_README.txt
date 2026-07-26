Atlas AI v2.5.0 - Integrated Feature Intelligence Foundation

This patch upgrades Atlas from 2.2.1 to 2.5.0 and adds the first integrated 2.x research-platform milestone.

Included:
- Modular plugin-style feature registry
- 72 engineered features across trend, momentum, volatility, volume, and quality
- Wide feature store: data/market/features_v2.csv
- Feature dictionary: reports/atlas_v2/feature_dictionary.json
- Feature statistics: reports/atlas_v2/feature_statistics.json
- Backward-compatible legacy feature store and market snapshot
- Feature provenance metadata and deterministic feature ordering
- New tests for registry integrity and generated artifacts

Install:
1. Extract this ZIP into the project root and allow replacement.
2. Activate the existing virtual environment.
3. Run:

   pip install -e ".[dev]"
   ruff check .
   mypy .
   pytest

4. Generate features from existing history:

   python scripts\atlas_v2_2_market_intelligence.py

Expected new outputs:
- data\market\features_v2.csv
- reports\atlas_v2\feature_dictionary.json
- reports\atlas_v2\feature_statistics.json

Safety:
- paper_trading_enabled remains false
- live_trading_enabled remains false

Validation performed in the build environment:
- Python compileall passed
- Atlas market test suite passed (8 tests)
- Full suite could not be completed in the build container because pyarrow was not installed there; your project environment already has pyarrow and previously passed the full suite.
