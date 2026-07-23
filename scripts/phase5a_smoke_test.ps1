$ErrorActionPreference = "Stop"

function Invoke-Step($Description, $Command) {
    Write-Host "`nRunning: $Description"
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

$TempRoot = Join-Path $env:TEMP "quant-phase5a-smoke"
Remove-Item -Recurse -Force $TempRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $TempRoot | Out-Null

Invoke-Step "Generate demo data" "python -m src.main data-demo --symbol OPTDEMO --rows 120"
Invoke-Step "Run optimization" "python -m src.main optimize-run --path data/validated/stock/OPTDEMO.parquet --param fast_period=5,10 --param slow_period=20,30 --method grid --objective sharpe --report-name phase5a_smoke"
Invoke-Step "Run research tests" "python -m pytest tests/unit/test_research_search.py tests/unit/test_research_objectives.py tests/unit/test_research_engine.py tests/unit/test_research_report.py tests/integration/test_optimization_cli.py"
Write-Host "Phase 5A optimization smoke test passed."
