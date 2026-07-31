# ATLAS v18 Complete Decision Intelligence

This overlay adds the complete v18 decision layer in one safe build:

- Market-regime classification
- Regime-aware strategy voting
- Confidence-weighted ensemble decisions
- Volatility-, confidence-, drawdown-, and exposure-aware position sizing
- Performance analytics (return, volatility, Sharpe, Sortino, drawdown, Calmar,
  win rate, profit factor, expectancy)
- Fail-closed live safety layer
- End-to-end decision orchestrator
- JSON demonstration CLI
- Unit tests

## Safety posture

The build does not submit broker orders. The live safety layer defaults to:

- kill switch enabled
- manual approval required
- broker heartbeat unhealthy until explicitly confirmed

Therefore a generated signal cannot become a live order by default.
