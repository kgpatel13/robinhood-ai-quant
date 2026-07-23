$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param([string]$Description, [scriptblock]$Command)
    Write-Host ""
    Write-Host "Running: $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Write-Host "Preparing Python 3.12 virtual environment..."
if (Test-Path .venv) {
    $version = & .\.venv\Scripts\python.exe --version 2>$null
    if ($LASTEXITCODE -ne 0) { Remove-Item -Recurse -Force .venv }
}
if (-not (Test-Path .venv)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv .venv }
    else { throw "Python launcher not found. Install Python 3.12." }
    if ($LASTEXITCODE -ne 0) { throw "Unable to create Python 3.12 virtual environment." }
}
Invoke-CheckedCommand "Upgrade pip" { .\.venv\Scripts\python.exe -m pip install --upgrade pip }
Invoke-CheckedCommand "Install project" { .\.venv\Scripts\python.exe -m pip install -e ".[dev]" }
Invoke-CheckedCommand "Health check" { .\.venv\Scripts\python.exe -m src.main healthcheck }
Invoke-CheckedCommand "Configuration validation" { .\.venv\Scripts\python.exe -m src.main config-validate }
Invoke-CheckedCommand "Offline data demo" { .\.venv\Scripts\python.exe -m src.main data-demo --symbol SETUP-DEMO --rows 400 }
Invoke-CheckedCommand "Quality checks" { .\scripts\run_checks.ps1 }
Invoke-CheckedCommand "Phase 3 smoke test" { .\scripts\phase3_smoke_test.ps1 }
Write-Host ""
Write-Host "Phases 1, 2, and 3 setup completed successfully."
