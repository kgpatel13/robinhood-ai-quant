$ErrorActionPreference = "Stop"
Write-Host "==> Phase 14 research intelligence smoke run"
python .\scripts\phase14_research_intelligence.py `
  --executed-trades .\reports\phase13_portfolio_engine_smoke\executed_trades.csv `
  --rejected-signals .\reports\phase13_portfolio_engine_smoke\rejected_signals.csv `
  --equity-curve .\reports\phase13_portfolio_engine_smoke\portfolio_equity_curve.csv `
  --output .\reports\phase14_research_intelligence_smoke
Write-Host "==> Ruff format check"
python -m ruff format --check .
Write-Host "==> Ruff lint check"
python -m ruff check .
Write-Host "==> Mypy check"
python -m mypy .
Write-Host "==> Pytest suite"
python -m pytest
Write-Host "Phase 14.9 quality gate passed."
