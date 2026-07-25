$ErrorActionPreference = "Stop"
function Invoke-Step($Label, $Command) {
    Write-Host "==> $Label"
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}
Invoke-Step "Phase 11 dataset smoke build" 'python .\scripts\phase11_dataset.py --data-root .\data\validated --dataset .\data\ml_dataset\phase11_smoke.parquet --output .\reports\phase11_dataset_smoke --symbols AAPL BTC-USD --stride 10'
Invoke-Step "Ruff format check" 'python -m ruff format --check .'
Invoke-Step "Ruff lint check" 'python -m ruff check .'
Invoke-Step "Mypy check" 'python -m mypy .'
Invoke-Step "Pytest suite" 'python -m pytest'
Write-Host "Phase 11.0 quality gate passed."
