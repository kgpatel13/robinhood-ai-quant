$ErrorActionPreference = "Stop"
Write-Host "==> Phase 13 portfolio engine smoke run"
python .\scripts\phase13_portfolio_engine.py `
  --trades .\reports\phase12_research_validation_smoke\simulated_trades.csv `
  --output .\reports\phase13_portfolio_engine_smoke
Write-Host "==> Ruff format check"
python -m ruff format --check .
Write-Host "==> Ruff lint check"
python -m ruff check .
Write-Host "==> Mypy check"
python -m mypy .
Write-Host "==> Pytest suite"
python -m pytest
Write-Host "Phase 13.9 quality gate passed."
