$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "Phase 10.2 robustness smoke replay" {
    python .\scripts\phase10_bundle.py `
        --symbols SPY AAPL BTC-USD `
        --signal-stride 20 `
        --output reports\phase10_smoke
}
Invoke-Checked "Ruff format check" { python -m ruff format --check . }
Invoke-Checked "Ruff lint check" { python -m ruff check . }
Invoke-Checked "Mypy check" { python -m mypy src scripts }
Invoke-Checked "Pytest suite" { python -m pytest }
Write-Host "Phase 10.1 quality gate passed."
