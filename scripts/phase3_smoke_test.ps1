$ErrorActionPreference = "Stop"
function Invoke-CheckedCommand {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "`nRunning: $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}
$Python = ".\.venv\Scripts\python.exe"
$DemoPath = "data\validated\stock\PHASE2-DEMO.parquet"
Invoke-CheckedCommand "Create demo data" { & $Python -m src.main data-demo --symbol PHASE2-DEMO --rows 400 }
Invoke-CheckedCommand "Run Phase 3 backtest" { & $Python -m src.main backtest-run --path $DemoPath --strategy moving_average_cross --fast 20 --slow 50 }
Write-Host "`nPhase 3 smoke test passed."
