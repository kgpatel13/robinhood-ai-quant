ATLAS AI v3.0 - PHASE 2: ALPHA & RANKING ENGINE
================================================

INSTALL
-------
1. Back up your project.
2. Extract this patch into the project root and overwrite files when prompted.
3. Activate your virtual environment.
4. Install/update the project if needed:

   python -m pip install -e ".[dev]"

VALIDATE
--------
Run from the project root:

   python -m pytest tests/test_atlas_factors.py tests/test_atlas_ranking.py
   python -m pytest
   python -m ruff check src tests scripts
   python -m mypy src

GENERATE PHASE 2 REPORTS
------------------------
First refresh the market feature store if needed:

   python -m scripts.atlas_v2_2_market_intelligence

Then run Phase 2:

   python -m scripts.atlas_v3_alpha_ranking

Optional parameters:

   python -m scripts.atlas_v3_alpha_ranking --top-n 50 --bottom-n 20

OUTPUTS
-------
reports/atlas_v3/factor_scores.csv
reports/atlas_v3/ranked_assets.csv
reports/atlas_v3/factor_statistics.json
reports/atlas_v3/factor_correlations.json
reports/atlas_v3/factor_dictionary.json
reports/atlas_v3/top_opportunities.json
reports/atlas_v3/ranking_summary.json

NOTES
-----
- This phase ranks research candidates; it does not place trades.
- Rankings are cross-sectional and are only as broad as features_v2.csv.
- The current sample feature store contains 142 assets, not the full 13,274-asset registry.
- Use python -m scripts.atlas_v3_alpha_ranking rather than running the file path directly.
