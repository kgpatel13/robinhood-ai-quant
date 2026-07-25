Phase 14.5 Portfolio Engine Repair — v0.14.5

Replace/merge these files into C:\Projects\robinhood-ai-quant.

Main repairs:
- Bounded 30-day drawdown circuit-breaker cooldown.
- Separate risk peak from all-time reporting peak.
- Circuit breaker can recover instead of remaining permanently locked.
- Every realized exit is written to the equity curve.
- Final equity reconciles exactly with cumulative realized P&L.
- Regression tests cover circuit-breaker recovery and equity reconciliation.

Run full production repair:

python .\scripts\phase13_portfolio_engine.py `
  --trades .\reports\phase12_research_validation\simulated_trades.csv `
  --output .\reports\phase13_portfolio_engine

Then rerun Phase 14:

python .\scripts\phase14_research_intelligence.py `
  --executed-trades .\reports\phase13_portfolio_engine\executed_trades.csv `
  --rejected-signals .\reports\phase13_portfolio_engine\rejected_signals.csv `
  --equity-curve .\reports\phase13_portfolio_engine\portfolio_equity_curve.csv `
  --output .\reports\phase14_research_intelligence

Quality gate:

powershell -ExecutionPolicy Bypass -File .\scripts\phase14_5_smoke_test.ps1

Reference validation against the supplied production dataset:
- Source trades: 8,677
- Executed trades: 3,328
- Rejected trades: 5,349
- Execution coverage: 100%
- Circuit-breaker rejection share: 3.94%
- Final capital: $48,129.83 from $10,000
- Total return: 381.30%
- CAGR: 4.60%
- Sharpe: 0.63
- Maximum drawdown: 25.70%
- Equity reconciliation difference: effectively $0
- Phase 15 review gate: approved

Paper and live trading remain disabled.
