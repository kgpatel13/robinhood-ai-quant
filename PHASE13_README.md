# Phase 13 — Professional Portfolio and Risk Engine

This replacement package adds Phase 13.0–13.9 without enabling broker execution.

It consumes Phase 12 `simulated_trades.csv`, applies confidence/volatility sizing,
portfolio exposure limits, concurrent-position controls, daily-loss protection,
and a portfolio drawdown circuit breaker.

Run the smoke gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\phase13_smoke_test.ps1
```

Run production:

```powershell
python .\scripts\phase13_portfolio_engine.py `
  --trades .\reports\phase12_research_validation\simulated_trades.csv `
  --output .\reports\phase13_portfolio_engine `
  --initial-capital 10000
```
