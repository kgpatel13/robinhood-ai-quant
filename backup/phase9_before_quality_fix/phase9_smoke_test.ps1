$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Invoke-CheckedCommand "Phase 9 smoke scan" {
    python .\scripts\phase9_bundle.py --symbols SPY QQQ BTC-USD --top-n 5 --output reports\phase9_smoke
}
Invoke-CheckedCommand "Ruff format check" {
    python -m ruff format --check src scripts tests
}
Invoke-CheckedCommand "Ruff lint check" {
    python -m ruff check src scripts tests
}
Invoke-CheckedCommand "Mypy check" {
    python -m mypy src scripts
}
Invoke-CheckedCommand "Pytest suite" {
    python -m pytest
}

Write-Host "Phase 9 quality gate passed."
