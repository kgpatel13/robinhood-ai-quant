$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Description,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "Running: $Description"

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

$Python = ".\.venv\Scripts\python.exe"
$DemoPath = "data\validated\stock\PHASE2-DEMO.parquet"

Invoke-CheckedCommand "Create offline demo data" {
    & $Python -m src.main data-demo --symbol PHASE2-DEMO
}

Invoke-CheckedCommand "Display dataset catalog" {
    & $Python -m src.main data-status
}

Invoke-CheckedCommand "Validate offline demo data" {
    & $Python -m src.main data-validate --path $DemoPath
}

Write-Host ""
Write-Host "Phase 2 offline smoke test passed."