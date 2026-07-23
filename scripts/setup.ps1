$ErrorActionPreference = "Stop"

Write-Host "Creating Python virtual environment..."

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3.12 -m venv .venv
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
}
else {
    throw "Python was not found. Install Python 3.11 or 3.12."
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m src.main healthcheck
& .\.venv\Scripts\python.exe -m src.main config-validate
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m mypy src

Write-Host ""
Write-Host "Phase 1 setup completed successfully."
Write-Host "Activate later with: .\.venv\Scripts\Activate.ps1"
