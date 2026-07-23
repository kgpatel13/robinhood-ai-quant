$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param([string]$Description, [scriptblock]$Command)
    Write-Host ""
    Write-Host "Running: $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

Invoke-CheckedCommand "Create first demo dataset" {
    .\.venv\Scripts\python.exe -m src.main data-demo --symbol PHASE4-A --rows 400
}
Invoke-CheckedCommand "Create second demo dataset" {
    .\.venv\Scripts\python.exe -m src.main data-demo --symbol PHASE4-B --rows 400
}
Invoke-CheckedCommand "Run Phase 4 portfolio backtest" {
    .\.venv\Scripts\python.exe -m src.main portfolio-backtest-run `
        --asset PHASE4-A=data\validated\stock\PHASE4-A.parquet `
        --asset PHASE4-B=data\validated\stock\PHASE4-B.parquet `
        --strategy moving_average_cross `
        --fast 20 `
        --slow 50 `
        --allocation equal `
        --rebalance weekly `
        --max-asset-weight 0.60 `
        --report-name phase4_smoke
}
Write-Host ""
Write-Host "Phase 4 portfolio smoke test passed."
