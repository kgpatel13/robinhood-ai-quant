$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param([string]$Description, [scriptblock]$Command)
    Write-Host ""
    Write-Host "Running: $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Invoke-CheckedCommand "pytest" { .\.venv\Scripts\python.exe -m pytest }
Invoke-CheckedCommand "Ruff linting" { .\.venv\Scripts\python.exe -m ruff check . }
Invoke-CheckedCommand "Ruff formatting" { .\.venv\Scripts\python.exe -m ruff format --check . }
Invoke-CheckedCommand "mypy" { .\.venv\Scripts\python.exe -m mypy src }
Write-Host ""
Write-Host "All Phase 1 and Phase 2 checks passed."
