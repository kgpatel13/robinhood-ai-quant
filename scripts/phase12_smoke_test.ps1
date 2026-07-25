$ErrorActionPreference = "Stop"
function Invoke-Step($Label, $Command) {
    Write-Host "==> $Label"
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}
Invoke-Step "Phase 12 research validation smoke run" 'python .\scripts\phase12_research_validation.py --dataset .\data\ml_dataset\phase11_smoke.parquet --phase11-champions .\reports\phase11_model_intelligence_smoke\champion_models.csv --output .\reports\phase12_research_validation_smoke --horizons 20 10 --maximum-rows-per-horizon 4000 --folds 2 --minimum-train-timestamps 100'
Invoke-Step "Ruff format check" 'python -m ruff format --check .'
Invoke-Step "Ruff lint check" 'python -m ruff check .'
Invoke-Step "Mypy check" 'python -m mypy .'
Invoke-Step "Pytest suite" 'python -m pytest'
Write-Host "Phase 12.9 quality gate passed."
