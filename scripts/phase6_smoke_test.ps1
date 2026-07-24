$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Invoke-Checked "Compile Python sources" { python -m compileall -q src scripts tests }
Invoke-Checked "Run tests" { python -m pytest }
Invoke-Checked "Run Ruff lint" { ruff check . }
Invoke-Checked "Check Ruff formatting" { ruff format --check . }
Invoke-Checked "Run mypy" { mypy src }
Write-Host "Phase 6 quality gate passed."
