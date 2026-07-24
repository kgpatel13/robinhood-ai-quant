$ErrorActionPreference = "Stop"

function Invoke-Step($Description, $Command) {
    Write-Host "==> $Description"
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Invoke-Step "Compile Python sources" "python -m compileall -q src scripts"
Invoke-Step "Run tests" "pytest"
Invoke-Step "Run Ruff lint" "ruff check ."
Invoke-Step "Check Ruff formatting" "ruff format --check ."
Invoke-Step "Run mypy" "mypy src"
Write-Host "Phase 8 quality gate passed."
