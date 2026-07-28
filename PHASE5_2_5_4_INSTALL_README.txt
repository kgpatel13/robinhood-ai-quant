Phase 5.2-5.4 Combined Intelligence Release

Included:
- Phase 5.2: ML opportunity ranking with deterministic fallback
- Phase 5.3: confidence- and regime-aware dynamic sizing
- Phase 5.4: adaptive portfolio construction and provider integration

Activation example:

from src.strategies import (
    AdaptiveMarketRegimeDetector,
    AdaptivePortfolioConstructor,
    MLOpportunityRanker,
)

provider = ShortSwingTargetProvider(
    bars_provider,
    regime_detector=AdaptiveMarketRegimeDetector(),
    opportunity_ranker=MLOpportunityRanker(),
    portfolio_constructor=AdaptivePortfolioConstructor(),
)

The provider model name becomes short-swing-ensemble-v3-ml-adaptive.
Without the ranker/constructor pair, existing v1/v2 behavior remains unchanged.

Training:
- Build OpportunityTrainingRow records using point-in-time features and realized forward labels.
- Call ranker.fit(rows).
- If data is insufficient or labels are one-sided, the ranker safely uses deterministic fallback scoring.
- Do not train on future data or random train/test splits; use chronological or walk-forward validation.

Local validation:
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest
