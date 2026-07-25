$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Write-Host "==> Prepare Phase 15 smoke data"
Invoke-Checked -Description "Smoke-data preparation" -Command {
    python -c "import zipfile; zipfile.ZipFile('phase12_research_validation_reports.zip').extract('simulated_trades.csv', 'reports/phase15_smoke_input')"
}

Write-Host "==> Phase 15 AI alpha engine smoke run"
Invoke-Checked -Description "Phase 15 smoke run" -Command {
    python .\scripts\phase15_alpha_engine.py `
      --trades .\reports\phase15_smoke_input\simulated_trades.csv `
      --output .\reports\phase15_alpha_engine_smoke `
      --folds 3 `
      --minimum-train-rows 500
}

Write-Host "==> Ruff format check"
Invoke-Checked -Description "Ruff format check" -Command { python -m ruff format --check . }

Write-Host "==> Ruff lint check"
Invoke-Checked -Description "Ruff lint check" -Command { python -m ruff check . }

Write-Host "==> Mypy check"
Invoke-Checked -Description "Mypy check" -Command { python -m mypy . }

Write-Host "==> Pytest suite"
Invoke-Checked -Description "Pytest suite" -Command { python -m pytest }

Write-Host "Phase 15.9 quality gate passed."
