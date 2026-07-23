$ErrorActionPreference = "Stop"

function Invoke-Phase5Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Invoke-Phase5Step "Compile Python sources" { python -m compileall -q src scripts }
Invoke-Phase5Step "Run tests" { python -m pytest }
Invoke-Phase5Step "Run Ruff lint" { python -m ruff check . }
Invoke-Phase5Step "Check Ruff formatting" { python -m ruff format --check . }
Invoke-Phase5Step "Run mypy" { python -m mypy src }
Invoke-Phase5Step "Run Phase 5 functional smoke test" {
    python .\scripts\phase5_bundle.py `
        --symbols SPY QQQ BTC-USD `
        --output reports\phase5_smoke
}

Write-Host "Phase 5 complete smoke test passed." -ForegroundColor Green
