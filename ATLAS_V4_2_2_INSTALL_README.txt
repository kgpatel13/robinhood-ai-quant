Atlas Phase 4.2.2 - Portfolio Intelligence

Added:
- src/atlas/portfolio/analytics.py
- scripts/atlas_v4_intelligence.py
- tests/test_atlas_portfolio_analytics.py
- atlas-intelligence console command

Capabilities:
- Historical annualized return and volatility
- Sharpe, Sortino, Calmar
- Maximum drawdown, downside deviation
- Historical and parametric VaR, CVaR
- Benchmark beta, alpha, tracking error, information ratio
- Correlation and covariance matrices
- Entropy, HHI, effective positions, diversification benefit
- Market-cap exposure buckets
- Portfolio scorecard and paper-trading readiness status
- Standalone HTML dashboard

Install:
  python -m pip install -e ".[dev]"

Run portfolio first:
  python -m scripts.atlas_v4_portfolio --capital 100000

Run intelligence:
  python -m scripts.atlas_v4_intelligence

Or:
  atlas-intelligence

Generated files:
  reports/atlas_v4/intelligence/portfolio_intelligence.json
  reports/atlas_v4/intelligence/portfolio_scorecard.json
  reports/atlas_v4/intelligence/correlation_matrix.csv
  reports/atlas_v4/intelligence/covariance_matrix.csv
  reports/atlas_v4/intelligence/portfolio_dashboard.html

Validation:
  python -m ruff check src tests scripts
  python -m mypy src
  python -m pytest

Container validation completed:
- New Phase 4.2.2 tests: 4 passed
- Python compilation: passed
- Full suite was blocked only because the container lacks pyarrow; the user's project dependency already includes pyarrow.
